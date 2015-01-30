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
  var composeMatrix = (function() {
    function multiply(a, b) {
      var result = [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]];
      for (var i = 0; i < 4; i++) {
        for (var j = 0; j < 4; j++) {
          for (var k = 0; k < 4; k++) {
            result[i][j] += b[i][k] * a[k][j];
          }
        }
      }
      return result;
    }

    function is2D(m) {
      return (
          m[0][2] == 0 &&
          m[0][3] == 0 &&
          m[1][2] == 0 &&
          m[1][3] == 0 &&
          m[2][0] == 0 &&
          m[2][1] == 0 &&
          m[2][2] == 1 &&
          m[2][3] == 0 &&
          m[3][2] == 0 &&
          m[3][3] == 1);
    }

    function composeMatrix(translate, scale, skew, quat, perspective) {
      var matrix = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]];

      for (var i = 0; i < 4; i++) {
        matrix[i][3] = perspective[i];
      }

      for (var i = 0; i < 3; i++) {
        for (var j = 0; j < 3; j++) {
          matrix[3][i] += translate[j] * matrix[j][i];
        }
      }

      var x = quat[0], y = quat[1], z = quat[2], w = quat[3];

      var rotMatrix = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]];

      rotMatrix[0][0] = 1 - 2 * (y * y + z * z);
      rotMatrix[0][1] = 2 * (x * y - z * w);
      rotMatrix[0][2] = 2 * (x * z + y * w);
      rotMatrix[1][0] = 2 * (x * y + z * w);
      rotMatrix[1][1] = 1 - 2 * (x * x + z * z);
      rotMatrix[1][2] = 2 * (y * z - x * w);
      rotMatrix[2][0] = 2 * (x * z - y * w);
      rotMatrix[2][1] = 2 * (y * z + x * w);
      rotMatrix[2][2] = 1 - 2 * (x * x + y * y);

      matrix = multiply(matrix, rotMatrix);

      var temp = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]];
      if (skew[2]) {
        temp[2][1] = skew[2];
        matrix = multiply(matrix, temp);
      }

      if (skew[1]) {
        temp[2][1] = 0;
        temp[2][0] = skew[0];
        matrix = multiply(matrix, temp);
      }

      if (skew[0]) {
        temp[2][0] = 0;
        temp[1][0] = skew[0];
        matrix = multiply(matrix, temp);
      }

      for (var i = 0; i < 3; i++) {
        for (var j = 0; j < 3; j++) {
          matrix[i][j] *= scale[i];
        }
      }

      if (is2D(matrix)) {
        return [matrix[0][0], matrix[0][1], matrix[1][0], matrix[1][1], matrix[3][0], matrix[3][1]];
      }
      return matrix[0].concat(matrix[1], matrix[2], matrix[3]);
    }
    return composeMatrix;
  })();

  function clamp(x, min, max) {
    return Math.max(Math.min(x, max), min);
  };

  function quat(fromQ, toQ, f) {
    var product = scope.dot(fromQ, toQ);
    product = clamp(product, -1.0, 1.0);

    var quat = [];
    if (product === 1.0) {
      quat = fromQ;
    } else {
      var theta = Math.acos(product);
      var w = Math.sin(f * theta) * 1 / Math.sqrt(1 - product * product);

      for (var i = 0; i < 4; i++) {
        quat.push(fromQ[i] * (Math.cos(f * theta) - product * w) +
                  toQ[i] * w);
      }
    }
    return quat;
  }

  scope.composeMatrix = composeMatrix;
  scope.quat = quat;

})(webAnimations1, webAnimationsTesting);
