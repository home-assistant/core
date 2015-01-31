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

(function(shared, scope) {

  scope.AnimationNode = function(timing) {
    var timeFraction = 0;
    var activeDuration = shared.calculateActiveDuration(timing);
    var animationNode = function(localTime) {
      return shared.calculateTimeFraction(activeDuration, localTime, timing);
    };
    animationNode._totalDuration = timing.delay + activeDuration + timing.endDelay;
    animationNode._isCurrent = function(localTime) {
      var phase = shared.calculatePhase(activeDuration, localTime, timing);
      return phase === PhaseActive || phase === PhaseBefore;
    };
    return animationNode;
  };

})(webAnimationsShared, webAnimations1);
