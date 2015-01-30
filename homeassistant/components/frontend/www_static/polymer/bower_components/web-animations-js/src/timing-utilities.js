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

(function(shared, testing) {

  var fills = 'backwards|forwards|both'.split('|');
  var directions = 'reverse|alternate|alternate-reverse'.split('|');

  function makeTiming(timingInput, forGroup) {
    var timing = {
      delay: 0,
      endDelay: 0,
      fill: forGroup ? 'both' : 'none',
      iterationStart: 0,
      iterations: 1,
      duration: forGroup ? 'auto' : 0,
      playbackRate: 1,
      direction: 'normal',
      easing: 'linear',
    };
    if (typeof timingInput == 'number' && !isNaN(timingInput)) {
      timing.duration = timingInput;
    } else if (timingInput !== undefined) {
      Object.getOwnPropertyNames(timingInput).forEach(function(property) {
        if (timingInput[property] != 'auto') {
          if (typeof timing[property] == 'number' || property == 'duration') {
            if (typeof timingInput[property] != 'number' || isNaN(timingInput[property])) {
              return;
            }
          }
          if ((property == 'fill') && (fills.indexOf(timingInput[property]) == -1)) {
            return;
          }
          if ((property == 'direction') && (directions.indexOf(timingInput[property]) == -1)) {
            return;
          }
          if (property == 'playbackRate' && shared.isDeprecated('AnimationTiming.playbackRate', '2014-11-28', 'Use AnimationPlayer.playbackRate instead.')) {
            return;
          }
          timing[property] = timingInput[property];
        }
      });
    }
    return timing;
  }

  function normalizeTimingInput(timingInput, forGroup) {
    var timing = makeTiming(timingInput, forGroup);
    timing.easing = toTimingFunction(timing.easing);
    return timing;
  }

  function cubic(a, b, c, d) {
    if (a < 0 || a > 1 || c < 0 || c > 1) {
      return linear;
    }
    return function(x) {
      var start = 0, end = 1;
      while (1) {
        var mid = (start + end) / 2;
        function f(a, b, m) { return 3 * a * (1 - m) * (1 - m) * m + 3 * b * (1 - m) * m * m + m * m * m};
        var xEst = f(a, c, mid);
        if (Math.abs(x - xEst) < 0.001) {
          return f(b, d, mid);
        }
        if (xEst < x) {
          start = mid;
        } else {
          end = mid;
        }
      }
    }
  }

  var Start = 1;
  var Middle = 0.5;
  var End = 0;

  function step(count, pos) {
    return function(x) {
      if (x >= 1) {
        return 1;
      }
      var stepSize = 1 / count;
      x += pos * stepSize;
      return x - x % stepSize;
    }
  }

  var presets = {
    'ease': cubic(0.25, 0.1, 0.25, 1),
    'ease-in': cubic(0.42, 0, 1, 1),
    'ease-out': cubic(0, 0, 0.58, 1),
    'ease-in-out': cubic(0.42, 0, 0.58, 1),
    'step-start': step(1, Start),
    'step-middle': step(1, Middle),
    'step-end': step(1, End)
  };

  var numberString = '\\s*(-?\\d+\\.?\\d*|-?\\.\\d+)\\s*';
  var cubicBezierRe = new RegExp('cubic-bezier\\(' + numberString + ',' + numberString + ',' + numberString + ',' + numberString + '\\)');
  var stepRe = /steps\(\s*(\d+)\s*,\s*(start|middle|end)\s*\)/;
  var linear = function(x) { return x; };

  function toTimingFunction(easing) {
    var cubicData = cubicBezierRe.exec(easing);
    if (cubicData) {
      return cubic.apply(this, cubicData.slice(1).map(Number));
    }
    var stepData = stepRe.exec(easing);
    if (stepData) {
      return step(Number(stepData[1]), {'start': Start, 'middle': Middle, 'end': End}[stepData[2]]);
    }
    var preset = presets[easing];
    if (preset) {
      return preset;
    }
    return linear;
  };

  function calculateActiveDuration(timing) {
    return Math.abs(repeatedDuration(timing) / timing.playbackRate);
  }

  function repeatedDuration(timing) {
    return timing.duration * timing.iterations;
  }

  var PhaseNone = 0;
  var PhaseBefore = 1;
  var PhaseAfter = 2;
  var PhaseActive = 3;

  function calculatePhase(activeDuration, localTime, timing) {
    if (localTime == null) {
      return PhaseNone;
    }
    if (localTime < timing.delay) {
      return PhaseBefore;
    }
    if (localTime >= timing.delay + activeDuration) {
      return PhaseAfter;
    }
    return PhaseActive;
  }

  function calculateActiveTime(activeDuration, fillMode, localTime, phase, delay) {
    switch (phase) {
      case PhaseBefore:
        if (fillMode == 'backwards' || fillMode == 'both')
          return 0;
        return null;
      case PhaseActive:
        return localTime - delay;
      case PhaseAfter:
        if (fillMode == 'forwards' || fillMode == 'both')
          return activeDuration;
        return null;
      case PhaseNone:
        return null;
    }
  }

  function calculateScaledActiveTime(activeDuration, activeTime, startOffset, timing) {
    return (timing.playbackRate < 0 ? activeTime - activeDuration : activeTime) * timing.playbackRate + startOffset;
  }

  function calculateIterationTime(iterationDuration, repeatedDuration, scaledActiveTime, startOffset, timing) {
    if (scaledActiveTime === Infinity || scaledActiveTime === -Infinity || (scaledActiveTime - startOffset == repeatedDuration && timing.iterations && ((timing.iterations + timing.iterationStart) % 1 == 0))) {
      return iterationDuration;
    }

    return scaledActiveTime % iterationDuration;
  }

  function calculateCurrentIteration(iterationDuration, iterationTime, scaledActiveTime, timing) {
    if (scaledActiveTime === 0) {
      return 0;
    }
    if (iterationTime == iterationDuration) {
      return timing.iterationStart + timing.iterations - 1;
    }
    return Math.floor(scaledActiveTime / iterationDuration);
  }

  function calculateTransformedTime(currentIteration, iterationDuration, iterationTime, timing) {
    var currentIterationIsOdd = currentIteration % 2 >= 1;
    var currentDirectionIsForwards = timing.direction == 'normal' || timing.direction == (currentIterationIsOdd ? 'alternate-reverse' : 'alternate');
    var directedTime = currentDirectionIsForwards ? iterationTime : iterationDuration - iterationTime;
    var timeFraction = directedTime / iterationDuration;
    return iterationDuration * timing.easing(timeFraction);
  }

  function calculateTimeFraction(activeDuration, localTime, timing) {
    var phase = calculatePhase(activeDuration, localTime, timing);
    var activeTime = calculateActiveTime(activeDuration, timing.fill, localTime, phase, timing.delay);
    if (activeTime === null)
      return null;
    if (activeDuration === 0)
      return phase === PhaseBefore ? 0 : 1;
    var startOffset = timing.iterationStart * timing.duration;
    var scaledActiveTime = calculateScaledActiveTime(activeDuration, activeTime, startOffset, timing);
    var iterationTime = calculateIterationTime(timing.duration, repeatedDuration(timing), scaledActiveTime, startOffset, timing);
    var currentIteration = calculateCurrentIteration(timing.duration, iterationTime, scaledActiveTime, timing);
    return calculateTransformedTime(currentIteration, timing.duration, iterationTime, timing) / timing.duration;
  }

  shared.makeTiming = makeTiming;
  shared.normalizeTimingInput = normalizeTimingInput;
  shared.calculateActiveDuration = calculateActiveDuration;
  shared.calculateTimeFraction = calculateTimeFraction;
  shared.calculatePhase = calculatePhase;
  shared.toTimingFunction = toTimingFunction;

  if (WEB_ANIMATIONS_TESTING) {
    testing.normalizeTimingInput = normalizeTimingInput;
    testing.toTimingFunction = toTimingFunction;
    testing.calculateActiveDuration = calculateActiveDuration;
    testing.calculatePhase = calculatePhase;
    testing.PhaseNone = PhaseNone;
    testing.PhaseBefore = PhaseBefore;
    testing.PhaseActive = PhaseActive;
    testing.PhaseAfter = PhaseAfter;
    testing.calculateActiveTime = calculateActiveTime;
    testing.calculateScaledActiveTime = calculateScaledActiveTime;
    testing.calculateIterationTime = calculateIterationTime;
    testing.calculateCurrentIteration = calculateCurrentIteration;
    testing.calculateTransformedTime = calculateTransformedTime;
  }

})(webAnimationsShared, webAnimationsTesting);
