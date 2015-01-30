suite('group-player-finish-event', function() {
  setup(function() {
    document.timeline.currentTime = undefined;
    this.element = document.createElement('div');
    document.documentElement.appendChild(this.element);
    var animation = new AnimationSequence([
      new Animation(this.element, [], 500),
      new AnimationGroup([
        new Animation(this.element, [], 250),
        new Animation(this.element, [], 500),
      ]),
    ]);
    this.player = document.timeline.play(animation, 1000);
  });
  teardown(function() {
    if (this.element.parent)
      this.element.removeChild(this.element);
  });

  test('fire when player completes', function(done) {
    var ready = false;
    var fired = false;
    var player = this.player;
    player.onfinish = function(event) {
      assert(ready, 'must not be called synchronously');
      assert.equal(this, player);
      assert.equal(event.target, player);
      assert.equal(event.currentTime, 1000);
      assert.equal(event.timelineTime, 1100);
      if (fired)
        assert(false, 'must not get fired twice');
      fired = true;
      done();
    };
    tick(100);
    tick(1100);
    tick(2100);
    ready = true;
  });

  test('fire when reversed player completes', function(done) {
    this.player.onfinish = function(event) {
      assert.equal(event.currentTime, 0);
      assert.equal(event.timelineTime, 1001);
      done();
    };
    tick(0);
    tick(500);
    this.player.reverse();
    tick(501);
    tick(1001);
  });

  test('fire after player is cancelled', function(done) {
    this.player.onfinish = function(event) {
      assert.equal(event.currentTime, 0);
      assert.equal(event.timelineTime, 1, 'event must be fired on next sample');
      done();
    };
    tick(0);
    this.player.cancel();
    tick(1);
  });

  test('multiple event listeners', function(done) {
    var count = 0;
    function createHandler(expectedCount) {
      return function() {
        count++;
        assert.equal(count, expectedCount);
      };
    }
    var toRemove = createHandler(0);
    this.player.addEventListener('finish', createHandler(1));
    this.player.addEventListener('finish', createHandler(2));
    this.player.addEventListener('finish', toRemove);
    this.player.addEventListener('finish', createHandler(3));
    this.player.removeEventListener('finish', toRemove);
    this.player.onfinish = function() {
      assert.equal(count, 3);
      done();
    };
    tick(0);
    this.player.cancel();
    tick(1000);
  });
});
