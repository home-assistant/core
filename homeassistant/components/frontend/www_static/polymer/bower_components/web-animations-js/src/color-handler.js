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

  var canvas = document.createElementNS('http://www.w3.org/1999/xhtml', 'canvas');
  canvas.width = canvas.height = 1;
  var context = canvas.getContext('2d');

  function parseColor(string) {
    string = string.trim();
    // The context ignores invalid colors
    context.fillStyle = '#000';
    context.fillStyle = string;
    var contextSerializedFillStyle = context.fillStyle;
    context.fillStyle = '#fff';
    context.fillStyle = string;
    if (contextSerializedFillStyle != context.fillStyle)
      return;
    context.fillRect(0, 0, 1, 1);
    var pixelColor = context.getImageData(0, 0, 1, 1).data;
    context.clearRect(0, 0, 1, 1);
    var alpha = pixelColor[3] / 255;
    return [pixelColor[0] * alpha, pixelColor[1] * alpha, pixelColor[2] * alpha, alpha];
  }

  function mergeColors(left, right) {
    return [left, right, function(x) {
      function clamp(v) {
        return Math.max(0, Math.min(255, v));
      }
      if (x[3]) {
        for (var i = 0; i < 3; i++)
          x[i] = Math.round(clamp(x[i] / x[3]));
      }
      x[3] = scope.numberToString(scope.clamp(0, 1, x[3]));
      return 'rgba(' + x.join(',') + ')';
    }];
  }

  scope.addPropertiesHandler(parseColor, mergeColors,
      ['background-color', 'border-bottom-color', 'border-left-color', 'border-right-color',
       'border-top-color', 'color', 'outline-color', 'text-decoration-color']);
  scope.consumeColor = scope.consumeParenthesised.bind(null, parseColor);
  scope.mergeColors = mergeColors;

  if (WEB_ANIMATIONS_TESTING) {
    testing.parseColor = parseColor;
  }

})(webAnimations1, webAnimationsTesting);
