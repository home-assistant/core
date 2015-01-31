// Copyright 2014 Google Inc. All rights reserved.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
//   You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//   See the License for the specific language governing permissions and
// limitations under the License.

(function(scope, testing) {

  function numberToString(x) {
    return x.toFixed(3).replace('.000', '');
  }

  function clamp(min, max, x) {
    return Math.min(max, Math.max(min, x));
  }

  function parseNumber(string) {
    if (/^\s*[-+]?(\d*\.)?\d+\s*$/.test(string))
      return Number(string);
  }

  function mergeNumbers(left, right) {
    return [left, right, numberToString];
  }

  // FIXME: This should probably go in it's own handler.
  function mergeFlex(left, right) {
    if (left == 0)
      return;
    return clampedMergeNumbers(0, Infinity)(left, right);
  }

  function mergePositiveIntegers(left, right) {
    return [left, right, function(x) {
      return Math.round(clamp(1, Infinity, x));
    }];
  }

  function clampedMergeNumbers(min, max) {
    return function(left, right) {
      return [left, right, function(x) {
        return numberToString(clamp(min, max, x));
      }];
    };
  }

  function round(left, right) {
    return [left, right, Math.round];
  }

  scope.clamp = clamp;
  scope.addPropertiesHandler(parseNumber, clampedMergeNumbers(0, Infinity), ['border-image-width', 'line-height']);
  scope.addPropertiesHandler(parseNumber, clampedMergeNumbers(0, 1), ['opacity', 'shape-image-threshold']);
  scope.addPropertiesHandler(parseNumber, clampedMergeNumbers(0.01, Infinity), ['zoom']);
  scope.addPropertiesHandler(parseNumber, mergeFlex, ['flex-grow', 'flex-shrink']);
  scope.addPropertiesHandler(parseNumber, mergeNumbers, ['zoom']);
  scope.addPropertiesHandler(parseNumber, mergePositiveIntegers, ['orphans', 'widows']);
  scope.addPropertiesHandler(parseNumber, round, ['z-index']);

  scope.parseNumber = parseNumber;
  scope.mergeNumbers = mergeNumbers;
  scope.numberToString = numberToString;

})(webAnimations1, webAnimationsTesting);
