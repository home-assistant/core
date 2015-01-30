suite('group-constructors', function() {
  setup(function() {
    document.timeline._players = [];
  });

  function simpleAnimationGroup() {
    return new AnimationSequence([
      new Animation(document.body, [], 2000),
      new AnimationGroup([
        new Animation(document.body, [], 2000),
        new Animation(document.body, [], 1000)
      ])
    ]);
  }

  test('player getter for children in groups, and __internalPlayer, work as expected', function() {
    var p = document.timeline.play(simpleAnimationGroup());
    tick(0);
    assert.equal(p.source.player, p);
    assert.equal(p._childPlayers[0].source.player, p);
    assert.equal(p._childPlayers[1].source.player, p);
    tick(2100);
    assert.equal(p._childPlayers[1]._childPlayers[0].source.player, p);
    assert.equal(p._childPlayers[1]._childPlayers[1].source.player, p);
  });
});
