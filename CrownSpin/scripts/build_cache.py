"""Local compiler reuse; retained products never depend on mutable DerivedData."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import shutil
import signal
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
CACHE_ROOT = Path.home() / "Library/Caches/EndlessCrown/Builds"
OUTPUT_SETTINGS = ("OBJROOT", "SYMROOT", "BUILD_DIR", "BUILD_ROOT", "DERIVED_DATA_DIR",
                   "CONFIGURATION_BUILD_DIR", "CONFIGURATION_TEMP_DIR", "PROJECT_TEMP_DIR",
                   "SHARED_PRECOMPS_DIR", "CLANG_MODULE_CACHE_PATH", "SWIFT_MODULE_CACHE_PATH",
                   "MODULE_CACHE_DIR", "XCODE_XCCONFIG_FILE")
INPUT_SETTINGS = ("ARCHS", "EXCLUDED_ARCHS", "ONLY_ACTIVE_ARCH", "SDKROOT", "SWIFT_VERSION",
                  "TOOLCHAINS", "SWIFT_EXEC", "CC", "CXX", "LD", "ENABLE_TESTABILITY",
                  "SWIFT_OPTIMIZATION_LEVEL", "GCC_OPTIMIZATION_LEVEL", "OTHER_SWIFT_FLAGS",
                  "OTHER_CFLAGS", "OTHER_CPLUSPLUSFLAGS", "OTHER_LDFLAGS",
                  "SWIFT_ACTIVE_COMPILATION_CONDITIONS", "GCC_PREPROCESSOR_DEFINITIONS",
                  "DEVELOPMENT_TEAM", "CODE_SIGN_IDENTITY", "CODE_SIGNING_ALLOWED",
                  "CODE_SIGNING_REQUIRED", "CODE_SIGN_STYLE", "OTHER_CODE_SIGN_FLAGS",
                  "PROVISIONING_PROFILE_SPECIFIER", "PROVISIONING_PROFILE")
SIGNALS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)


def internal_path(value):
    path = Path(value).expanduser().resolve()
    if path == Path("/Volumes") or Path("/Volumes") in path.parents:
        raise ValueError("External storage support is deferred; use internal storage.")
    return path


def validate_output(value):
    output, cache = internal_path(value), internal_path(CACHE_ROOT)
    if output == cache or output in cache.parents or cache in output.parents:
        raise ValueError("Compiler caches and retained reports/products need separate roots.")
    source = ROOT / "CrownSpin"
    if output == source or source in output.parents:
        raise ValueError("Keep retained output outside the CrownSpin source directory.")
    return output


def query(command, env):
    return subprocess.check_output(command, env=env, text=True).strip()


def recipe(command, env, profile):
    overrides = [name for name in OUTPUT_SETTINGS if env.get(name)]
    overrides += [arg.split("=", 1)[0] for arg in command if arg.split("=", 1)[0] in OUTPUT_SETTINGS]
    if overrides:
        raise ValueError("Unmanaged compiler output overrides: " + ", ".join(sorted(set(overrides))))
    normalized = []
    project = None
    index = 0
    while index < len(command):
        arg = command[index]
        if arg in ("-derivedDataPath", "-resultBundlePath"):
            index += 2
            continue
        if arg == "-project":
            project = Path(command[index + 1]).resolve()
            normalized += [arg, "checkout-project"]
            index += 2
            continue
        if not arg.startswith(("ENERGY_SOURCE_REVISION=", "ENERGY_SOURCE_FINGERPRINT=")):
            normalized.append(arg)
        index += 1
    if project is None or command.count("-derivedDataPath") != 1:
        raise ValueError("Expected one project and one managed DerivedData argument.")
    files = [project / "project.pbxproj", *sorted((project / "xcshareddata/xcschemes").glob("*.xcscheme"))]
    project_hash = hashlib.sha256(b"".join(str(p.relative_to(project)).encode() + b"\0" + p.read_bytes() for p in files)).hexdigest()
    developer = internal_path(env.get("DEVELOPER_DIR") or query(["xcode-select", "-p"], env))
    if developer.suffix == ".app":
        developer = developer / "Contents/Developer"
    sdk = "watchsimulator" if any("watchOS Simulator" in arg for arg in command) else "watchos"
    return {"checkout": str(ROOT), "profile": profile, "command": normalized, "project": project_hash,
            "developer": str(developer), "xcode": query([command[0], "-version"], env),
            "sdk": query(["xcrun", "--sdk", sdk, "--show-sdk-path"], env),
            "sdkBuild": query(["xcrun", "--sdk", sdk, "--show-sdk-build-version"], env),
            "hostArchitecture": platform.machine(),
            "settings": {key: env[key] for key in INPUT_SETTINGS if key in env}}


def live_group(pid):
    rows = subprocess.check_output(["/bin/ps", "-axo", "pgid=,stat="], text=True)
    return any(len(parts) == 2 and parts[0] == str(pid) and not parts[1].startswith("Z")
               for parts in (line.split() for line in rows.splitlines()))


def signal_group(pid, signum):
    try:
        os.killpg(pid, signum)
    except ProcessLookupError:
        pass
    except PermissionError:
        if live_group(pid):
            raise


def drain(child):
    # Keep the lease until the leader AND its remaining compiler writers stop.
    if live_group(child.pid):
        signal_group(child.pid, signal.SIGTERM)
        deadline = time.monotonic() + 2
        while live_group(child.pid) and time.monotonic() < deadline:
            time.sleep(.05)
        if live_group(child.pid):
            signal_group(child.pid, signal.SIGKILL)
        while live_group(child.pid):
            time.sleep(.05)
    child.wait()


def save(path, value):
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def retained_build(output):
    """Resolve a convenience pointer once; callers keep the returned generation."""
    output = internal_path(output)
    pointer = output / "latest-build.json"
    if pointer.is_file():
        output = Path(json.loads(pointer.read_text())["build"])
    return internal_path(output)


def snapshot(products, destination):
    # Preserve signed bundle symlinks, but never retain links back into a cache.
    for path in products.rglob("*"):
        if path.is_symlink() and (path.readlink().is_absolute() or not path.resolve().is_relative_to(products)):
            raise ValueError("Built products contain an external/absolute symlink: " + str(path))
    shutil.copytree(products, destination, symlinks=True)
    for path in destination.glob("*.xctestrun"):
        def resolve(value):
            if isinstance(value, dict):
                return {key: resolve(child) for key, child in value.items()}
            if isinstance(value, list):
                return [resolve(child) for child in value]
            if isinstance(value, str):
                return value.replace(str(products), str(destination)).replace("__DERIVEDDATA__", str(destination.parents[1]))
            return value
        path.write_bytes(plistlib.dumps(resolve(plistlib.loads(path.read_bytes()))))


def build_products(command, *, output, env, log=None, fresh=False, profile="automation", validate=None):
    output = validate_output(output)
    identity = recipe(command, env, profile)
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:24]
    workspace = internal_path(CACHE_ROOT) / (key + ("-fresh-" + uuid.uuid4().hex if fresh else ""))
    if workspace.is_symlink():
        raise ValueError("Compiler workspace must not be a symlink.")
    workspace.mkdir(parents=True, exist_ok=True)
    generation = output / ("build-" + uuid.uuid4().hex)
    generation.mkdir(parents=True)
    metadata = {"state": "waiting", "cacheKey": key, "workspace": str(workspace),
                "build": str(generation), "fresh": fresh, "recipe": identity}
    record = generation / "build.json"
    save(record, metadata)
    child = None
    launching = False
    received = []

    def cancel(signum, frame):
        received.append(signum)
        if not launching:
            raise SystemExit(128 + signum)

    previous = {sig: signal.signal(sig, cancel) for sig in SIGNALS}
    try:
        descriptor = os.open(workspace / ".build.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            for name in ("DerivedData", "Temporary"):
                if (workspace / name).is_symlink():
                    raise ValueError("Compiler directories must not be symlinks.")
                (workspace / name).mkdir(exist_ok=True)
            derived = workspace / "DerivedData"
            actual = list(command)
            actual[actual.index("-derivedDataPath") + 1] = str(derived)
            build_env = dict(env, TMPDIR=str(workspace / "Temporary") + "/")
            metadata.update(state="building", command=actual)
            save(record, metadata)
            own_log = (generation / "build.log").open("w") if log is None else None
            try:
                launching = True
                try:
                    child = subprocess.Popen(actual, cwd=ROOT, env=build_env, stdout=log or own_log,
                                             stderr=subprocess.STDOUT, start_new_session=True, pass_fds=(lock.fileno(),))
                finally:
                    launching = False
                if received:
                    raise SystemExit(128 + received[-1])
                code = child.wait()
            finally:
                ignored = {sig: signal.signal(sig, signal.SIG_IGN) for sig in SIGNALS}
                try:
                    if child is not None:
                        drain(child)
                        child = None
                finally:
                    for sig, handler in ignored.items():
                        signal.signal(sig, handler)
                    if own_log:
                        own_log.close()
            if code:
                raise subprocess.CalledProcessError(code, actual)
            snapshot(derived / "Build/Products", generation / "Build/Products")
            if validate:
                validate(generation)
            metadata["state"] = "ready"
            save(record, metadata)
            save(output / "latest-build.json", {"build": str(generation)})
        return generation
    except BaseException as error:
        metadata.update(state="failed", error=f"{type(error).__name__}: {error}")
        save(record, metadata)
        raise
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
