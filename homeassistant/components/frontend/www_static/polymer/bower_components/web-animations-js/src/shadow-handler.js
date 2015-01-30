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

  function consumeShadow(string) {
    var shadow = {
      inset: false,
      lengths: [],
      color: null,
    };
    function consumePart(string) {
      var result = scope.consumeToken(/^inset/i, string);
      if (result) {
        shadow.inset = true;
        return result;
      }
      var result = scope.consumeLengthOrPercent(string);
      if (result) {
        shadow.lengths.push(result[0]);
        return result;
      }
      var result = scope.consumeColor(string);
      if (result) {
        shadow.color = result[0];
        return result;
      }
    }
    var result = scope.consumeRepeated(consumePart, /^/, string);
    if (result && result[0].length) {
      return [shadow, result[1]];
    }
  }

  function parseShadowList(string) {
    var result = scope.consumeRepeated(consumeShadow, /^,/, string);
    if (result && result[1] == '') {
      return result[0];
    }
  }

  function mergeShadow(left, right) {
    while (left.lengths.length < Math.max(left.lengths.length, right.lengths.length))
      left.lengths.push({px: 0});
    while (right.lengths.length < Math.max(left.lengths.length, right.lengths.length))
      right.lengths.push({px: 0});

    if (left.inset != right.inset || !!left.color != !!right.color) {
      return;
    }
    var lengthReconstitution = [];
    var colorReconstitution;
    var matchingLeft = [[], 0];
    var matchingRight = [[], 0];
    for (var i = 0; i < left.lengths.length; i++) {
      var mergedDimensions = scope.mergeDimensions(left.lengths[i], right.lengths[i], i == 2);
      matchingLeft[0].push(mergedDimensions[0]);
      matchingRight[0].push(mergedDimensions[1]);
      lengthReconstitution.push(mergedDimensions[2]);
    }
    if (left.color && right.color) {
      var mergedColor = scope.mergeColors(left.color, right.color);
      matchingLeft[1] = mergedColor[0];
      matchingRight[1] = mergedColor[1];
      colorReconstitution = mergedColor[2];
    }
    return [matchingLeft, matchingRight, function(value) {
      var result = left.inset ? 'inset ' : ' ';
      for (var i = 0; i < lengthReconstitution.length; i++) {
        result += lengthReconstitution[i](value[0][i]) + ' ';
      }
      if (colorReconstitution) {
        result += colorReconstitution(value[1]);
      }
      return result;
    }];
  }

  function mergeNestedRepeatedShadow(nestedMerge, separator, left, right) {
    var leftCopy = [];
    var rightCopy = [];
    function defaultShadow(inset) {
      return {inset: inset, color: [0, 0, 0, 0], lengths: [{px: 0}, {px: 0}, {px: 0}, {px: 0}]};
    }
    for (var i = 0; i < left.length || i < right.length; i++) {
      var l = left[i] || defaultShadow(right[i].inset);
      var r = right[i] || defaultShadow(left[i].inset);
      leftCopy.push(l);
      rightCopy.push(r);
    }
    return scope.mergeNestedRepeated(nestedMerge, separator, leftCopy, rightCopy);
  }

  var mergeShadowList = mergeNestedRepeatedShadow.bind(null, mergeShadow, ', ');
  scope.addPropertiesHandler(parseShadowList, mergeShadowList, ['box-shadow', 'text-shadow']);

})(webAnimations1);
