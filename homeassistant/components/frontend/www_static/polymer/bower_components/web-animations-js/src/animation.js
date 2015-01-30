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

  scope.Animation = function(target, effectInput, timingInput) {
    var animationNode = scope.AnimationNode(shared.normalizeTimingInput(timingInput));
    var effect = scope.convertEffectInput(effectInput);
    var timeFraction;
    var animation = function() {
      WEB_ANIMATIONS_TESTING && console.assert(typeof timeFraction !== 'undefined');
      effect(target, timeFraction);
    };
    // Returns whether the animation is in effect or not after the timing update.
    animation._update = function(localTime) {
      timeFraction = animationNode(localTime);
      return timeFraction !== null;
    };
    animation._clear = function() {
      effect(target, null);
    };
    animation._hasSameTarget = function(otherTarget) {
      return target === otherTarget;
    };
    animation._isCurrent = animationNode._isCurrent;
    animation._totalDuration = animationNode._totalDuration;
    return animation;
  };

  scope.NullAnimation = function(clear) {
    var nullAnimation = function() {
      if (clear) {
        clear();
        clear = null;
      }
    };
    nullAnimation._update = function() {
      return null;
    };
    nullAnimation._totalDuration = 0;
    nullAnimation._isCurrent = function() {
      return false;
    };
    nullAnimation._hasSameTarget = function() {
      return false;
    };
    return nullAnimation;
  };

  if (WEB_ANIMATIONS_TESTING) {
    testing.webAnimations1Animation = scope.Animation;
  }

})(webAnimationsShared, webAnimations1, webAnimationsTesting);
