suite('animation-constructor', function() {
  setup(function() {
    document.timeline.getAnimationPlayers().forEach(function(player) {
      player.cancel();
    });
  });

  test('Playing an Animation makes a Player', function() {
    var animation = new Animation(document.body, [], 1000);
    assert.equal(document.body.getAnimationPlayers().length, 0);

    var player = document.timeline.play(animation);
    tick(200);
    assert.equal(document.body.getAnimationPlayers().length, 1);

    tick(1600);
    assert.equal(document.body.getAnimationPlayers().length, 0);
  });

  test('Setting the timing function on an Animation works', function() {
    function leftAsNumber(target) {
      left = getComputedStyle(target).left;
      return Number(left.substring(0, left.length - 2));
    }

    var target1 = document.createElement('div');
    var target2 = document.createElement('div');
    target1.style.position = 'absolute';
    target2.style.position = 'absolute';
    document.body.appendChild(target1);
    document.body.appendChild(target2);

    var animation1 = new Animation(target1, [{left: '0px'}, {left: '50px'}], 1000);
    var animation2 = new Animation(target2, [{left: '0px'}, {left: '50px'}], {duration: 1000, easing: 'ease-in'});

    var player1 = document.timeline.play(animation1);
    var player2 = document.timeline.play(animation2);

    tick(0);
    assert.equal(leftAsNumber(target1), 0);
    assert.equal(leftAsNumber(target2), 0);

    tick(250);
    assert.closeTo(leftAsNumber(target1), 12.5, 1);
    assert.closeTo(leftAsNumber(target2), 4.65, 1);

    tick(500);
    assert.closeTo(leftAsNumber(target1), 25, 1);
    assert.closeTo(leftAsNumber(target2), 15.25, 1);
  });

  test('Timing is always converted to AnimationTimingInput', function() {
    var target = document.createElement('div');
    document.body.appendChild(target);

    var keyframes = [{background: 'blue'}, {background: 'red'}];

    var animation = new Animation(target, keyframes, 200);
    assert.equal(animation.timing.duration, 200);

    animation = new Animation(target, keyframes);
    assert.isDefined(animation.timing);

    animation = new Animation(target, keyframes, {duration: 200});
    var group = new AnimationGroup([animation]);
    assert.equal(group.timing.duration, 'auto');
  });

  test('Handle null target on Animation', function() {
    var animation = new Animation(null, function(tf) {
      // noop
    }, 200);

    var player = document.timeline.play(animation);
    assert.isNotNull(player);
    tick(50);
    tick(150);
    assert.equal(player.currentTime, 100);
  });
});
