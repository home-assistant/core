suite('tick-tests', function() {
  setup(function() { webAnimations1.timeline._players = []; });

  test('players are in effect but ticking stops once forward fill is reached', function() {
    tick(90);
    var player = document.body.animate([], {duration: 1000, fill: 'forwards'});
    tick(100);
    tick(600);
    assert.equal(webAnimations1.timeline._players.length, 1);
    assert.equal(isTicking(), true);
    tick(1100);
    assert.equal(player.finished, true);
    assert.equal(webAnimations1.timeline._players.length, 1);
    assert.equal(isTicking(), false);
  });
});
