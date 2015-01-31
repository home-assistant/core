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
  var originalRequestAnimationFrame = window.requestAnimationFrame;
  var rafCallbacks = [];
  var rafId = 0;
  window.requestAnimationFrame = function(f) {
    var id = rafId++;
    if (rafCallbacks.length == 0 && !WEB_ANIMATIONS_TESTING) {
      originalRequestAnimationFrame(processRafCallbacks);
    }
    rafCallbacks.push([id, f]);
    return id;
  };

  window.cancelAnimationFrame = function(id) {
    rafCallbacks.forEach(function(entry) {
      if (entry[0] == id) {
        entry[1] = function() {};
      }
    });
  };

  function processRafCallbacks(t) {
    var processing = rafCallbacks;
    rafCallbacks = [];
    tick(t);
    processing.forEach(function(entry) { entry[1](t); });
    if (needsRetick)
      tick(t);
    applyPendingEffects();
  }

  function comparePlayers(leftPlayer, rightPlayer) {
    return leftPlayer._sequenceNumber - rightPlayer._sequenceNumber;
  }

  function InternalTimeline() {
    this._players = [];
    // Android 4.3 browser has window.performance, but not window.performance.now
    this.currentTime = window.performance && performance.now ? performance.now() : 0;
  };

  InternalTimeline.prototype = {
    _play: function(source) {
      source._timing = shared.normalizeTimingInput(source.timing);
      var player = new scope.Player(source);
      player._idle = false;
      player._timeline = this;
      this._players.push(player);
      scope.restart();
      scope.invalidateEffects();
      return player;
    }
  };

  var ticking = false;
  var hasRestartedThisFrame = false;

  scope.restart = function() {
    if (!ticking) {
      ticking = true;
      requestAnimationFrame(function() {});
      hasRestartedThisFrame = true;
    }
    return hasRestartedThisFrame;
  };

  var needsRetick = false;
  scope.invalidateEffects = function() {
    needsRetick = true;
  };

  var pendingEffects = [];
  function applyPendingEffects() {
    pendingEffects.forEach(function(f) { f(); });
  }

  var originalGetComputedStyle = window.getComputedStyle;
  Object.defineProperty(window, 'getComputedStyle', {
    configurable: true,
    enumerable: true,
    value: function() {
      if (needsRetick) tick(timeline.currentTime);
      applyPendingEffects();
      return originalGetComputedStyle.apply(this, arguments);
    },
  });

  function tick(t) {
    hasRestartedThisFrame = false;
    var timeline = scope.timeline;
    timeline.currentTime = t;
    timeline._players.sort(comparePlayers);
    ticking = false;
    var updatingPlayers = timeline._players;
    timeline._players = [];

    var newPendingClears = [];
    var newPendingEffects = [];
    updatingPlayers = updatingPlayers.filter(function(player) {
      player._inTimeline = player._tick(t);

      if (!player._inEffect)
        newPendingClears.push(player._source);
      else
        newPendingEffects.push(player._source);

      if (!player.finished && !player.paused && !player._idle)
        ticking = true;

      return player._inTimeline;
    });

    pendingEffects.length = 0;
    pendingEffects.push.apply(pendingEffects, newPendingClears);
    pendingEffects.push.apply(pendingEffects, newPendingEffects);

    timeline._players.push.apply(timeline._players, updatingPlayers);
    needsRetick = false;

    if (ticking)
      requestAnimationFrame(function() {});
  };

  if (WEB_ANIMATIONS_TESTING) {
    testing.tick = processRafCallbacks;
    testing.isTicking = function() { return ticking; };
    testing.setTicking = function(newVal) { ticking = newVal; };
  }

  var timeline = new InternalTimeline();
  scope.timeline = timeline;

})(webAnimationsShared, webAnimations1, webAnimationsTesting);
