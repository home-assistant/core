suite('timeline-tests', function() {
  setup(function() {
    document.timeline._players = [];
    webAnimations1.timeline._players = [];
  });

  test('no current players', function() {
    assert.equal(document.timeline.getAnimationPlayers().length, 0);
  });

  test('getAnimationPlayers', function() {
    tick(90);
    assert.equal(document.timeline.getAnimationPlayers().length, 0);
    var player = document.body.animate([], {duration: 500, iterations: 1});
    tick(300);
    assert.equal(document.timeline.getAnimationPlayers().length, 1);

    var player2 = document.body.animate([], {duration: 1000});
    assert.equal(document.timeline.getAnimationPlayers().length, 2);
    tick(800);
    assert.equal(player.finished, true);
    assert.equal(document.timeline.getAnimationPlayers().length, 1);
    tick(2000);
    assert.equal(document.timeline.getAnimationPlayers().length, 0);
  });

  test('getAnimationPlayers checks cancelled animation', function() {
    tick(90);
    assert.equal(document.timeline.getAnimationPlayers().length, 0);
    var player = document.body.animate([], {duration: 500, iterations: 1});
    tick(300);
    assert.equal(document.timeline.getAnimationPlayers().length, 1);
    player.cancel();
    assert.equal(document.timeline.getAnimationPlayers().length, 0);
  });
});
