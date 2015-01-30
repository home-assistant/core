suite('timing', function() {
  setup(function() {
    webAnimations1.timeline._players = [];
  });

  test('pause and scrub', function() {
    var player = document.body.animate([], { duration: 1000 });
    player.pause();

    player.currentTime = 500;
    assert.equal(player.currentTime, 500);
  });

  test('pause, scrub and play', function() {
    var target = document.createElement('div');
    document.body.appendChild(target);

    var player = target.animate([
      { background: 'blue' },
      { background: 'red' }
    ], { duration: 1000 });
    tick(100);
    player.pause();

    player.currentTime = 200;
    // http://www.w3.org/TR/web-animations/#the-current-time-of-a-player
    // currentTime should now mean 'hold time' - this allows scrubbing.
    assert.equal(player.currentTime, 200);
    player.play();

    tick(200);
    tick(300);
    assert.equal(player.currentTime, 300);
    assert.equal(player.startTime, 0);
  });

  test('sanity-check NaN timing', function() {
    // This has no actual tests, but will infinite loop without fix.

    var player = document.body.animate([], {
      duration: 2000,
      easing: 'ease-in'  // fails only with cubic easing, not linear
    });
    tick(100);
    player.currentTime = NaN;
    tick(200);

    player = document.body.animate([], { duration: NaN, easing: 'ease-out' });
    tick(300);
  });
});
