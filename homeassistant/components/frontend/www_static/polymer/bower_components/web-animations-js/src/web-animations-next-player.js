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
  scope.Player = function(source) {
    this.source = source;
    if (source) {
      // FIXME: detach existing player.
      source.player = this;
    }
    this._isGroup = false;
    this._player = null;
    this._childPlayers = [];
    this._callback = null;
    this._rebuildUnderlyingPlayer();
    // Players are constructed in the idle state.
    this._player.cancel();
  };

  // TODO: add a source getter/setter
  scope.Player.prototype = {
    _rebuildUnderlyingPlayer: function() {
      if (this._player) {
        this._player.cancel();
        this._player = null;
      }

      if (!this.source || this.source instanceof window.Animation) {
        this._player = scope.newUnderlyingPlayerForAnimation(this.source);
        scope.bindPlayerForAnimation(this);
      }
      if (this.source instanceof window.AnimationSequence || this.source instanceof window.AnimationGroup) {
        this._player = scope.newUnderlyingPlayerForGroup(this.source);
        scope.bindPlayerForGroup(this);
      }

      // FIXME: move existing currentTime/startTime/playState to new player
    },
    get paused() {
      return this._player.paused;
    },
    get playState() {
      return this._player.playState;
    },
    get onfinish() {
      return this._onfinish;
    },
    set onfinish(v) {
      if (typeof v == 'function') {
        this._onfinish = v;
        this._player.onfinish = (function(e) {
          e.target = this;
          v.call(this, e);
        }).bind(this);
      } else {
        this._player.onfinish = v;
        this.onfinish = this._player.onfinish;
      }
    },
    get currentTime() {
      return this._player.currentTime;
    },
    set currentTime(v) {
      this._player.currentTime = v;
      this._register();
      this._forEachChild(function(child, offset) {
        child.currentTime = v - offset;
      });
    },
    get startTime() {
      return this._player.startTime;
    },
    set startTime(v) {
      this._player.startTime = v;
      this._register();
      this._forEachChild(function(child, offset) {
        child.startTime = v + offset;
      });
    },
    get playbackRate() {
      return this._player.playbackRate;
    },
    get finished() {
      return this._player.finished;
    },
    play: function() {
      this._player.play();
      this._register();
      scope.awaitStartTime(this);
      this._forEachChild(function(child) {
        var time = child.currentTime;
        child.play();
        child.currentTime = time;
      });
    },
    pause: function() {
      this._player.pause();
      this._register();
      this._forEachChild(function(child) {
        child.pause();
      });
    },
    finish: function() {
      this._player.finish();
      this._register();
      // TODO: child players??
    },
    cancel: function() {
      this._player.cancel();
      this._register();
      this._removePlayers();
    },
    reverse: function() {
      this._player.reverse();
      scope.awaitStartTime(this);
      this._register();
      this._forEachChild(function(child, offset) {
        child.reverse();
        child.startTime = this.startTime + offset * this.playbackRate;
        child.currentTime = this.currentTime + offset * this.playbackRate;
      });
    },
    addEventListener: function(type, handler) {
      var wrapped = handler;
      if (typeof handler == 'function') {
        wrapped = (function(e) {
          e.target = this;
          handler.call(this, e);
        }).bind(this);
        handler._wrapper = wrapped;
      }
      this._player.addEventListener(type, wrapped);
    },
    removeEventListener: function(type, handler) {
      this._player.removeEventListener(type, (handler && handler._wrapper) || handler);
    },
    _removePlayers: function() {
      while (this._childPlayers.length)
        this._childPlayers.pop().cancel();
    },
    _forEachChild: function(f) {
      var offset = 0;
      this._childPlayers.forEach(function(child) {
        f.call(this, child, offset);
        if (this.source instanceof window.AnimationSequence)
          offset += child.source.activeDuration;
      }.bind(this));
    },
  };

})(webAnimationsShared, webAnimationsNext, webAnimationsTesting);
