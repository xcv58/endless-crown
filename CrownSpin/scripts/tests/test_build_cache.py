"""Owned fake-Xcode workflows. Never build, install or measure on a device."""
import argparse
from contextlib import ExitStack, redirect_stdout
import fcntl
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import plistlib
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).parents[1]


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


cache = module("cache", "build_cache.py")
energy = module("energy", "energy-tests.py")
haptic = module("haptic", "haptic-comparison.py")
system = module("system", "system-scroll-compare.py")

FAKE_XCODE = r'''#!/usr/bin/env python3
import json, os, pathlib, plistlib, subprocess, sys, time
if '-version' in sys.argv:
    print('Owned fake Xcode 1'); sys.exit(0)
dd = pathlib.Path(sys.argv[sys.argv.index('-derivedDataPath') + 1])
products = dd / 'Build/Products'; products.mkdir(parents=True, exist_ok=True)
events = dd / 'events'; events.open('a').write('start\n')
if os.environ.get('FAKE_WORKER'):
    code = "import pathlib,signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);p=pathlib.Path("+repr(str(dd/'heartbeat'))+");\nwhile True:\n p.open('a').write('tick\\n');time.sleep(.03)"
    subprocess.Popen([sys.executable, '-c', code])
    (dd / 'group-pid').write_text(str(os.getpgrp()))
    time.sleep(60)
time.sleep(float(os.environ.get('FAKE_DELAY', '0')))
fingerprint = next((a.split('=',1)[1] for a in sys.argv if a.startswith('ENERGY_SOURCE_FINGERPRINT=')), 'fake')
app = products / 'Release-watchos/CrownSpin Watch App.app'; app.mkdir(parents=True, exist_ok=True)
(app / 'Info.plist').write_bytes(plistlib.dumps({'EnergySourceFingerprint':fingerprint,'CFBundleIdentifier':'media.jenny.crownspin.watchapp'}))
(app / 'binary').write_text(os.environ.get('FAKE_PAYLOAD','first'))
if os.environ.get('FAKE_FAIL'): sys.exit(7)
runner=products/'Release-watchos/CrownSpinEnergyUITests-Runner.app';runner.mkdir(exist_ok=True)
(runner/'binary').write_text('runner-'+os.environ.get('FAKE_PAYLOAD','first'))
(products/'tests.xctestrun').write_bytes(plistlib.dumps({'TestTargets':[{'BlueprintName':'CrownSpinEnergyUITests','IsUITestBundle':True,'TestHostPath':str(runner),'ClangProfileDataDirectoryPath':'__DERIVEDDATA__/Build/ProfileData'}]}))
obj=dd/'cached-object';
if not obj.exists(): obj.write_text('cached')
events.open('a').write('end\n')
'''


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="crown-cache-fixture-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.checkout = self.root / "checkout"; self.checkout.mkdir()
        self.project = self.checkout / "CrownSpin/CrownSpin.xcodeproj"
        (self.project / "xcshareddata/xcschemes").mkdir(parents=True)
        (self.project / "project.pbxproj").write_text("fixture settings")
        (self.project / "xcshareddata/xcschemes/Energy.xcscheme").write_text("fixture scheme")
        (self.project.parent / "CrownSpinEnergyUITests").mkdir()
        (self.project.parent / "CrownSpinEnergyUITests/EnergyAutomationUITests.swift").write_text("fixture")
        self.bin = self.root / "bin"; self.bin.mkdir()
        for name, text in (("xcodebuild", FAKE_XCODE), ("xcrun", "#!/bin/sh\necho owned-fake-sdk\n"), ("codesign", "#!/bin/sh\nexit 0\n")):
            path = self.bin / name; path.write_text(text); path.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"], DEVELOPER_DIR=str(self.root / "Developer"))
        for key in cache.OUTPUT_SETTINGS + cache.INPUT_SETTINGS:
            self.env.pop(key, None)
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        for subject in (cache, energy.build_cache, haptic.energy.build_cache, system.energy.build_cache):
            self.stack.enter_context(patch.object(subject, "CACHE_ROOT", self.root / "cache"))
            self.stack.enter_context(patch.object(subject, "ROOT", self.checkout))
        self.command = ["xcodebuild", "build-for-testing", "-project", str(self.project), "-scheme", "Energy",
                        "-configuration", "Release", "-destination", "id=owned-fake-watch", "-derivedDataPath", "unused",
                        "SWIFT_ACTIVE_COMPILATION_CONDITIONS=$(inherited) ENERGY_TESTING", "ENERGY_SOURCE_FINGERPRINT=source-one"]

    def build(self, command=None, env=None, **kwargs):
        return cache.build_products(command or self.command, output=self.root / "reports", env=env or self.env, **kwargs)

    def metadata(self, generation):
        return json.loads((generation / "build.json").read_text())

    def wait_for(self, predicate):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if predicate(): return
            time.sleep(.02)
        self.fail("Owned workflow did not reach its expected boundary")

    def driver(self, name, *, env=None, slow_snapshot=False):
        output = self.root / name
        script = self.root / (name + '.py')
        script.write_text('import importlib.util,json,time\nfrom pathlib import Path\n' +
            's=importlib.util.spec_from_file_location("cache",' + repr(str(SCRIPTS / 'build_cache.py')) + ')\n' +
            'm=importlib.util.module_from_spec(s);s.loader.exec_module(m)\n' +
            'm.ROOT=Path(' + repr(str(self.checkout)) + ');m.CACHE_ROOT=Path(' + repr(str(self.root / 'cache')) + ')\n' +
            ('original=m.snapshot\ndef slow(products,destination):\n'
             ' events=products.parents[1]/"events";events.open("a").write("copy-start\\n")\n'
             ' Path(' + repr(str(self.root / 'copy-start')) + ').write_text("started")\n'
             ' time.sleep(.7);original(products,destination);events.open("a").write("copy-end\\n")\n'
             'm.snapshot=slow\n' if slow_snapshot else '') +
            'import os\nm.build_products(' + repr(self.command) + ',output=Path(' + repr(str(output)) + '),env=dict(os.environ))\n')
        log = (self.root / (name + '.log')).open('w'); self.addCleanup(log.close)
        process = subprocess.Popen([sys.executable, str(script)], env=env or self.env, stdout=log, stderr=subprocess.STDOUT)
        def cleanup():
            if process.poll() is None:
                process.kill(); process.wait()
            for path in (self.root / 'cache').glob('*/DerivedData/group-pid'):
                pid = int(path.read_text())
                try: os.killpg(pid, signal.SIGKILL)
                except ProcessLookupError: pass
                except PermissionError:
                    if cache.live_group(pid): raise
        self.addCleanup(cleanup)
        return process, output

    def test_concurrent_builder_waits_through_product_snapshot(self):
        first, output = self.driver('first', slow_snapshot=True)
        self.wait_for(lambda: (self.root / 'copy-start').is_file())
        second, other = self.driver('second')
        self.assertEqual(first.wait(timeout=10), 0)
        self.assertEqual(second.wait(timeout=10), 0)
        one = cache.retained_build(output); two = cache.retained_build(other)
        self.assertEqual(self.metadata(one)['workspace'], self.metadata(two)['workspace'])
        events = Path(self.metadata(one)['workspace']) / 'DerivedData/events'
        self.assertEqual(events.read_text().splitlines(), ['start', 'end', 'copy-start', 'copy-end', 'start', 'end'])

    def test_cancellation_holds_lease_until_resistant_descendant_stops(self):
        process, output = self.driver('cancel', env=dict(self.env, FAKE_WORKER='1'))
        self.wait_for(lambda: bool(list((self.root / 'cache').glob('*/DerivedData/heartbeat'))))
        workspace = next((self.root / 'cache').iterdir())
        process.send_signal(signal.SIGTERM)
        with (workspace / '.build.lock').open('a+') as lock:
            with self.assertRaises(BlockingIOError): fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.assertEqual(process.wait(timeout=10), 143)
        heartbeat = workspace / 'DerivedData/heartbeat'; size = heartbeat.stat().st_size
        time.sleep(.15)
        self.assertEqual(heartbeat.stat().st_size, size)
        self.assertFalse((output / 'latest-build.json').exists())
        with (workspace / '.build.lock').open('a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_failed_product_validation_keeps_previous_success_pointer(self):
        first = self.build()
        def invalid(generation): raise ValueError('owned invalid product')
        with self.assertRaisesRegex(ValueError, 'invalid product'): self.build(validate=invalid)
        self.assertEqual(cache.retained_build(self.root / 'reports'), first)

    def test_reuse_keeps_products_and_reports_independent_of_compiler(self):
        first = self.build()
        metadata = self.metadata(first); workspace = Path(metadata["workspace"])
        obj = workspace / "DerivedData/cached-object"; stamp = obj.stat().st_mtime_ns
        changed = [a.replace('source-one', 'source-two') for a in self.command] + ['ENERGY_SOURCE_REVISION=new-revision']
        second = self.build(changed, dict(self.env, FAKE_PAYLOAD="second"))
        self.assertEqual(metadata["workspace"], self.metadata(second)["workspace"])
        self.assertNotEqual(first, second)
        self.assertEqual(obj.stat().st_mtime_ns, stamp)
        self.assertEqual((first / "Build/Products/Release-watchos/CrownSpin Watch App.app/binary").read_text(), "first")
        self.assertEqual((second / "Build/Products/Release-watchos/CrownSpin Watch App.app/binary").read_text(), "second")
        self.assertNotIn(str(workspace), str(plistlib.loads((second / "Build/Products/tests.xctestrun").read_bytes())))
        self.assertFalse((first / "Build/Intermediates.noindex").exists())
        # Remove only owned fabricated cache data to prove report independence.
        import shutil
        shutil.rmtree(workspace)
        self.assertTrue((first / "Build/Products/tests.xctestrun").is_file())

    def test_failed_rebuild_does_not_publish_mixed_app_and_old_runner(self):
        first = self.build()
        with self.assertRaises(subprocess.CalledProcessError):
            self.build(env=dict(self.env, FAKE_FAIL="1", FAKE_PAYLOAD="bad"))
        self.assertEqual(cache.retained_build(self.root / "reports"), first)
        self.assertEqual((first / "Build/Products/Release-watchos/CrownSpinEnergyUITests-Runner.app/binary").read_text(), "runner-first")
        records = [self.metadata(p) for p in (self.root / "reports").glob("build-*")]
        self.assertEqual(sorted(p["state"] for p in records), ["failed", "ready"])

    def test_variants_signing_architecture_project_and_probes_separate_keys(self):
        baseline = cache.recipe(self.command, self.env, "automation")
        for command, env, profile in ((self.command + ["CODE_SIGNING_ALLOWED=NO"], self.env, "automation"),
                (self.command + ["OTHER_SWIFT_FLAGS=-DOTHER"], self.env, "automation"),
                (self.command, dict(self.env, ARCHS="arm64"), "automation"),
                (self.command, dict(self.env, DEVELOPMENT_TEAM="another-team"), "automation"),
                (self.command, dict(self.env, DEVELOPER_DIR=str(self.root / 'OtherDeveloper')), "automation"),
                ([a.replace('Release', 'Debug') for a in self.command], self.env, "automation"),
                ([a.replace('id=owned-fake-watch', 'id=other-watch') for a in self.command], self.env, "automation"),
                (self.command, self.env, "system-probe-A")):
            self.assertNotEqual(cache.recipe(command, env, profile), baseline)
        (self.project / "project.pbxproj").write_text("different settings")
        self.assertNotEqual(cache.recipe(self.command, self.env, "automation"), baseline)

    def test_fresh_uses_another_workspace_without_removing_old_cache(self):
        warm = self.build(); cold = self.build(fresh=True)
        self.assertNotEqual(self.metadata(warm)["workspace"], self.metadata(cold)["workspace"])
        self.assertEqual(self.metadata(warm)["cacheKey"], self.metadata(cold)["cacheKey"])
        self.assertTrue(Path(self.metadata(warm)["workspace"]).is_dir())

    def test_external_overlap_source_and_output_overrides_rejected(self):
        for output in (Path('/Volumes/External/reports'), self.root / 'cache/reports', self.checkout / 'CrownSpin/reports'):
            with self.assertRaises(ValueError): cache.build_products(self.command, output=output, env=self.env)
        for name in cache.OUTPUT_SETTINGS:
            with self.assertRaises(ValueError): self.build(env=dict(self.env, **{name: '/unmanaged'}))

    def test_product_symlink_cannot_retain_cache_dependency(self):
        source = self.root / "products"; source.mkdir()
        (source / "external").symlink_to(self.project / "project.pbxproj")
        with self.assertRaises(ValueError): cache.snapshot(source, self.root / "snapshot")

    def test_energy_and_haptic_and_system_callers_reuse_and_pin_generations(self):
        original_query = subprocess.check_output
        def query(command, **kwargs):
            return "fixture-revision\n" if command[0] == "git" else original_query(command, **kwargs)
        with patch.dict(os.environ, self.env, clear=True), patch.object(subprocess, "check_output", side_effect=query), redirect_stdout(io.StringIO()):
            for subject in (energy, haptic.energy, system.energy):
                self.stack.enter_context(patch.object(subject, "ROOT", self.checkout))
                self.stack.enter_context(patch.object(subject, "PROJECT", self.project))
                self.stack.enter_context(patch.object(subject, "source_fingerprint", return_value="fixture-source"))
            build_args = argparse.Namespace(device="owned-fake-watch", automation=True, variant="optimized", unsigned=False,
                allow_provisioning_updates=False, output=self.root / "automation", fresh_build=False)
            energy.build(build_args); first = cache.retained_build(build_args.output)
            energy.build(build_args); second = cache.retained_build(build_args.output)
            self.assertEqual(self.metadata(first)["workspace"], self.metadata(second)["workspace"])
            energy.automation_products(first, "optimized"); energy.automation_products(second, "optimized")
            # Exercise automate's builder but stop at its first native test boundary.
            original_run = subprocess.run
            def native_boundary(command, **kwargs):
                if command[:2] == ['xcodebuild', 'test-without-building']:
                    raise RuntimeError('owned native boundary')
                return original_run(command, **kwargs)
            args = argparse.Namespace(device='owned-fake-watch', variant='optimized', skip_build=False, fresh_build=False,
                seconds=15, repetitions=1, cooldown=0, cases='idle', steps_per_second=2, crown_delta=.5,
                crown_velocity=1, pause=.25, output=self.root / 'automation-runs', build_output=build_args.output,
                label='synthetic', pattern='clicks', conditions='fixture only', allow_provisioning_updates=False)
            with patch.object(subprocess, 'run', side_effect=native_boundary):
                with self.assertRaisesRegex(RuntimeError, 'owned native boundary'): energy.automate(args)
            self.assertTrue((args.build_output / 'energy-build.json').is_file())
            self.assertEqual(self.metadata(second)['workspace'], self.metadata(args.build_output)['workspace'])
            haptic_args = argparse.Namespace(device="owned-fake-watch", developer_dir=self.root / 'Developer', seconds=15,
                variants="before,overhead-only", output=self.root / 'haptics', rebuild_session=None, fresh_build=False)
            haptic.prepare(haptic_args); haptic.prepare(haptic_args)
            sessions = list(haptic_args.output.glob('*/comparison.json'))
            pairs = [json.loads(p.read_text()) for p in sessions]
            self.assertEqual({t['fingerprint'] for t in pairs[0]['trials']}, {t['fingerprint'] for t in pairs[1]['trials']})
            self.assertTrue(all(Path(t['app']).is_dir() and '/DerivedData/' not in t['app'] for m in pairs for t in m['trials']))
            normal = self.root / 'normal.json'; normal.write_text(json.dumps({'sourceFingerprint':'fixture-source'}))
            manifests=[]
            for name in ('system-one', 'system-two'):
                system.prepare(argparse.Namespace(session=self.root / name, device='owned-fake-watch',
                    developer_dir=str(self.root / 'Developer'), restore_normal=normal, fresh_build=False))
                manifests.append(json.loads((self.root / name / 'system-comparison.json').read_text()))
            self.assertEqual(self.metadata(Path(manifests[0]['build']))['workspace'], self.metadata(Path(manifests[1]['build']))['workspace'])
            self.assertNotEqual(manifests[0]['build'], manifests[1]['build'])
            for manifest in manifests: system.verify_products(manifest)


if __name__ == "__main__":
    unittest.main()
