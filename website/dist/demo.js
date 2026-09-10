(() => {
  const video = document.querySelector('#demo-video');
  const play = document.querySelector('#demo-play');
  const status = document.querySelector('#demo-status');
  if (!video || !play || !status) return;

  play.hidden = false;
  play.addEventListener('click', async () => {
    const moveFocus = document.activeElement === play;
    play.disabled = true;
    status.textContent = 'Loading the demo…';
    try {
      await video.play();
      status.textContent = '';
      // Keep keyboard users on a usable control when the overlay disappears.
      if (moveFocus) video.focus();
    } catch {
      play.hidden = false;
      status.textContent = 'The demo could not play. Try the player controls or read the video description below.';
    } finally {
      play.disabled = false;
    }
  });
  video.addEventListener('play', () => {
    play.hidden = true;
    status.textContent = '';
  });
  video.addEventListener('ended', () => {
    play.hidden = false;
    play.querySelector('[data-play-label]').textContent = 'Watch again · 27 sec';
  });
  video.addEventListener('error', () => {
    play.hidden = true;
    status.textContent = 'The demo could not load. Refresh the page to try again, or read the video description below.';
  });
})();
