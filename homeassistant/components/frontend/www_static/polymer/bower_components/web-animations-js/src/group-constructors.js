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

  function constructor(children, timingInput) {
    this.children = children || [];
    this._timing = shared.normalizeTimingInput(timingInput, true);
    this.timing = shared.makeTiming(timingInput, true);

    if (this._timing.duration === 'auto')
      this._timing.duration = this.activeDuration;
  }

  window.AnimationSequence = function() {
    constructor.apply(this, arguments);
  };

  window.AnimationGroup = function() {
    constructor.apply(this, arguments);
  };

  window.AnimationSequence.prototype = {
    get activeDuration() {
      var total = 0;
      this.children.forEach(function(child) {
        total += scope.groupChildDuration(child);
      });
      return Math.max(total, 0);
    }
  };

  window.AnimationGroup.prototype = {
    get activeDuration() {
      var max = 0;
      this.children.forEach(function(child) {
        max = Math.max(max, scope.groupChildDuration(child));
      });
      return max;
    }
  };

  scope.newUnderlyingPlayerForGroup = function(group) {
    var underlyingPlayer;
    var ticker = function(tf) {
      var player = underlyingPlayer._wrapper;
      if (!player.source)
        return;
      if (tf == null) {
        player._removePlayers();
        return;
      }
      if (player.startTime === null)
        return;

      player._updateChildren();
    };

    underlyingPlayer = scope.timeline.play(new scope.Animation(null, ticker, group._timing));
    return underlyingPlayer;
  };

  scope.bindPlayerForGroup = function(player) {
    player._player._wrapper = player;
    player._isGroup = true;
    scope.awaitStartTime(player);
    player._updateChildren();
  };


})(webAnimationsShared, webAnimationsNext, webAnimationsTesting);
