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

(function(scope) {

  var consumeLengthOrPercent = scope.consumeParenthesised.bind(null, scope.parseLengthOrPercent);
  var consumeLengthOrPercentPair = scope.consumeRepeated.bind(undefined, consumeLengthOrPercent, /^/);

  var mergeSizePair = scope.mergeNestedRepeated.bind(undefined, scope.mergeDimensions, ' ');
  var mergeSizePairList = scope.mergeNestedRepeated.bind(undefined, mergeSizePair, ',');

  function parseShape(input) {
    var circle = scope.consumeToken(/^circle/, input);
    if (circle && circle[0]) {
      return ['circle'].concat(scope.consumeList([
        scope.ignore(scope.consumeToken.bind(undefined, /^\(/)),
        consumeLengthOrPercent,
        scope.ignore(scope.consumeToken.bind(undefined, /^at/)),
        scope.consumePosition,
        scope.ignore(scope.consumeToken.bind(undefined, /^\)/))
      ], circle[1]));
    }
    var ellipse = scope.consumeToken(/^ellipse/, input);
    if (ellipse && ellipse[0]) {
      return ['ellipse'].concat(scope.consumeList([
        scope.ignore(scope.consumeToken.bind(undefined, /^\(/)),
        consumeLengthOrPercentPair,
        scope.ignore(scope.consumeToken.bind(undefined, /^at/)),
        scope.consumePosition,
        scope.ignore(scope.consumeToken.bind(undefined, /^\)/))
      ], ellipse[1]));
    }
    var polygon = scope.consumeToken(/^polygon/, input);
    if (polygon && polygon[0]) {
      return ['polygon'].concat(scope.consumeList([
        scope.ignore(scope.consumeToken.bind(undefined, /^\(/)),
        scope.optional(scope.consumeToken.bind(undefined, /^nonzero\s*,|^evenodd\s*,/), 'nonzero,'),
        scope.consumeSizePairList,
        scope.ignore(scope.consumeToken.bind(undefined, /^\)/))
      ], polygon[1]));
    }
  }

  function mergeShapes(left, right) {
    if (left[0] !== right[0])
      return;
    if (left[0] == 'circle') {
      return scope.mergeList(left.slice(1), right.slice(1), [
        'circle(',
        scope.mergeDimensions,
        ' at ',
        scope.mergeOffsetList,
        ')']);
    }
    if (left[0] == 'ellipse') {
      return scope.mergeList(left.slice(1), right.slice(1), [
        'ellipse(',
        scope.mergeNonNegativeSizePair,
        ' at ',
        scope.mergeOffsetList,
        ')']);
    }
    if (left[0] == 'polygon' && left[1] == right[1]) {
      return scope.mergeList(left.slice(2), right.slice(2), [
        'polygon(',
        left[1],
        mergeSizePairList,
        ')']);
    }
  }

  scope.addPropertiesHandler(parseShape, mergeShapes, ['shape-outside']);

})(webAnimations1);
