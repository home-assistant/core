// Copyright 2014 Google Inc. All rights reserved.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
//     You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//     See the License for the specific language governing permissions and
// limitations under the License.

(function(shared, scope, testing) {

  function groupChildDuration(node) {
    return node._timing.delay + node.activeDuration + node._timing.endDelay;
  };

  function KeyframeEffect(effect) {
    this._frames = shared.normalizeKeyframes(effect);
  }

  KeyframeEffect.prototype = {
    getFrames: function() { return this._frames; }
  };

  scope.Animation = function(target, effect, timingInput) {
    this.target = target;

    // TODO: Store a clone, not the same instance.
    this._timingInput = timingInput;
    this._timing = shared.normalizeTimingInput(timingInput);

    // TODO: Make modifications to timing update the underlying player
    this.timing = shared.makeTiming(timingInput);
    // TODO: Make this a live object - will need to separate normalization of
    // keyframes into a shared module.
    if (typeof effect == 'function')
      this.effect = effect;
    else
      this.effect = new KeyframeEffect(effect);
    this._effect = effect;
    this.activeDuration = shared.calculateActiveDuration(this._timing);
    return this;
  };

  var originalElementAnimate = Element.prototype.animate;
  Element.prototype.animate = function(effect, timing) {
    return scope.timeline.play(new scope.Animation(this, effect, timing));
  };

  var nullTarget = document.createElementNS('http://www.w3.org/1999/xhtml', 'div');
  scope.newUnderlyingPlayerForAnimation = function(animation) {
    var target = animation.target || nullTarget;
    var effect = animation._effect;
    if (typeof effect == 'function') {
      effect = [];
    }
    return originalElementAnimate.apply(target, [effect, animation._timingInput]);
  };

  scope.bindPlayerForAnimation = function(player) {
    if (player.source && typeof player.source.effect == 'function') {
      scope.bindPlayerForCustomEffect(player);
    }
  };

  var pendingGroups = [];
  scope.awaitStartTime = function(groupPlayer) {
    if (groupPlayer.startTime !== null || !groupPlayer._isGroup)
      return;
    if (pendingGroups.length == 0) {
      requestAnimationFrame(updatePendingGroups);
    }
    pendingGroups.push(groupPlayer);
  };
  function updatePendingGroups() {
    var updated = false;
    while (pendingGroups.length) {
      pendingGroups.shift()._updateChildren();
      updated = true;
    }
    return updated;
  }
  var originalGetComputedStyle = window.getComputedStyle;
  Object.defineProperty(window, 'getComputedStyle', {
    configurable: true,
    enumerable: true,
    value: function() {
      var result = originalGetComputedStyle.apply(this, arguments);
      if (updatePendingGroups())
        result = originalGetComputedStyle.apply(this, arguments);
      return result;
    },
  });

  // TODO: Call into this less frequently.
  scope.Player.prototype._updateChildren = function() {
    if (this.paused || !this.source || !this._isGroup)
      return;
    var offset = this.source._timing.delay;
    for (var i = 0; i < this.source.children.length; i++) {
      var child = this.source.children[i];
      var childPlayer;

      if (i >= this._childPlayers.length) {
        childPlayer = window.document.timeline.play(child);
        this._childPlayers.push(childPlayer);
      } else {
        childPlayer = this._childPlayers[i];
      }
      child.player = this.source.player;

      if (childPlayer.startTime != this.startTime + offset) {
        if (this.startTime === null) {
          childPlayer.currentTime = this.source.player.currentTime - offset;
          childPlayer._startTime = null;
        } else {
          childPlayer.startTime = this.startTime + offset;
        }
        childPlayer._updateChildren();
      }

      if (this.playbackRate == -1 && this.currentTime < offset && childPlayer.currentTime !== -1) {
        childPlayer.currentTime = -1;
      }

      if (this.source instanceof window.AnimationSequence)
        offset += groupChildDuration(child);
    }
  };

  window.Animation = scope.Animation;
  window.Element.prototype.getAnimationPlayers = function() {
    return document.timeline.getAnimationPlayers().filter(function(player) {
      return player.source !== null && player.source.target == this;
    }.bind(this));
  };

  scope.groupChildDuration = groupChildDuration;

}(webAnimationsShared, webAnimationsNext, webAnimationsTesting));
