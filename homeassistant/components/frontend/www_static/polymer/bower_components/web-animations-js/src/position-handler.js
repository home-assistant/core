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

  function negateDimension(dimension) {
    var result = {};
    for (var k in dimension) {
      result[k] = -dimension[k];
    }
    return result;
  }

  function consumeOffset(string) {
    return scope.consumeToken(/^(left|center|right|top|bottom)\b/i, string) || scope.consumeLengthOrPercent(string);
  }

  var offsetMap = {
    left: {'%': 0},
    center: {'%': 50},
    right: {'%': 100},
    top: {'%': 0},
    bottom: {'%': 100},
  };

  function parseOrigin(slots, string) {
    var result = scope.consumeRepeated(consumeOffset, /^/, string);
    if (!result || result[1] != '') return;
    var tokens = result[0];
    tokens[0] = tokens[0] || 'center';
    tokens[1] = tokens[1] || 'center';
    if (slots == 3) {
      tokens[2] = tokens[2] || {px: 0};
    }
    if (tokens.length != slots) {
      return;
    }
    // Reorder so that the horizontal axis comes first.
    if (/top|bottom/.test(tokens[0]) || /left|right/.test(tokens[1])) {
      var tmp = tokens[0];
      tokens[0] = tokens[1];
      tokens[1] = tmp;
    }
    // Invalid if not horizontal then vertical.
    if (!/left|right|center|Object/.test(tokens[0]))
      return;
    if (!/top|bottom|center|Object/.test(tokens[1]))
      return;
    return tokens.map(function(position) {
      return typeof position == 'object' ? position : offsetMap[position];
    });
  }

  var mergeOffsetList = scope.mergeNestedRepeated.bind(null, scope.mergeDimensions, ' ');
  scope.addPropertiesHandler(parseOrigin.bind(null, 3), mergeOffsetList, ['transform-origin']);
  scope.addPropertiesHandler(parseOrigin.bind(null, 2), mergeOffsetList, ['perspective-origin']);

  function consumePosition(string) {
    var result = scope.consumeRepeated(consumeOffset, /^/, string);
    if (!result) {
      return;
    }

    var tokens = result[0];
    var out = [{'%': 50}, {'%': 50}];
    var pos = 0;
    var bottomOrRight = false;

    for (var i = 0; i < tokens.length; i++) {
      var token = tokens[i];
      if (typeof token == 'string') {
        bottomOrRight = /bottom|right/.test(token);
        pos = {left: 0, right: 0, center: pos, top: 1, bottom: 1}[token];
        out[pos] = offsetMap[token];
        if (token == 'center') {
          // Center doesn't accept a length offset.
          pos++;
        }
      } else {
        if (bottomOrRight) {
          // If bottom or right we need to subtract the length from 100%
          token = negateDimension(token);
          token['%'] = (token['%'] || 0) + 100;
        }
        out[pos] = token;
        pos++;
        bottomOrRight = false;
      }
    }
    return [out, result[1]];
  }

  function parsePositionList(string) {
    var result = scope.consumeRepeated(consumePosition, /^,/, string);
    if (result && result[1] == '') {
      return result[0];
    }
  }

  scope.consumePosition = consumePosition;
  scope.mergeOffsetList = mergeOffsetList;

  var mergePositionList = scope.mergeNestedRepeated.bind(null, mergeOffsetList, ', ');
  scope.addPropertiesHandler(parsePositionList, mergePositionList, ['background-position', 'object-position']);

})(webAnimations1);
