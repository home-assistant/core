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
  function consumeLengthPercentOrAuto(string) {
    return scope.consumeLengthOrPercent(string) || scope.consumeToken(/^auto/, string);
  }
  function parseBox(string) {
    var result = scope.consumeList([
      scope.ignore(scope.consumeToken.bind(null, /^rect/)),
      scope.ignore(scope.consumeToken.bind(null, /^\(/)),
      scope.consumeRepeated.bind(null, consumeLengthPercentOrAuto, /^,/),
      scope.ignore(scope.consumeToken.bind(null, /^\)/)),
    ], string);
    if (result && result[0].length == 4) {
      return result[0];
    }
  }

  function mergeComponent(left, right) {
    if (left == 'auto' || right == 'auto') {
      return [true, false, function(t) {
        var result = t ? left : right;
        if (result == 'auto') {
          return 'auto';
        }
        // FIXME: There's probably a better way to turn a dimension back into a string.
        var merged = scope.mergeDimensions(result, result);
        return merged[2](merged[0]);
      }];
    }
    return scope.mergeDimensions(left, right);
  }

  function wrap(result) {
    return 'rect(' + result + ')';
  }

  var mergeBoxes = scope.mergeWrappedNestedRepeated.bind(null, wrap, mergeComponent, ', ');

  scope.parseBox = parseBox;
  scope.mergeBoxes = mergeBoxes;

  scope.addPropertiesHandler(parseBox, mergeBoxes, ['clip']);

})(webAnimations1, webAnimationsTesting);
