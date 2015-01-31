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
  var decomposeMatrix = (function() {
    function determinant(m) {
      return m[0][0] * m[1][1] * m[2][2] +
             m[1][0] * m[2][1] * m[0][2] +
             m[2][0] * m[0][1] * m[1][2] -
             m[0][2] * m[1][1] * m[2][0] -
             m[1][2] * m[2][1] * m[0][0] -
             m[2][2] * m[0][1] * m[1][0];
    }

    // from Wikipedia:
    //
    // [A B]^-1 = [A^-1 + A^-1B(D - CA^-1B)^-1CA^-1     -A^-1B(D - CA^-1B)^-1]
    // [C D]      [-(D - CA^-1B)^-1CA^-1                (D - CA^-1B)^-1      ]
    //
    // Therefore
    //
    // [A [0]]^-1 = [A^-1       [0]]
    // [C  1 ]      [ -CA^-1     1 ]
    function inverse(m) {
      var iDet = 1 / determinant(m);
      var a = m[0][0], b = m[0][1], c = m[0][2];
      var d = m[1][0], e = m[1][1], f = m[1][2];
      var g = m[2][0], h = m[2][1], k = m[2][2];
      var Ainv = [
        [(e * k - f * h) * iDet, (c * h - b * k) * iDet,
         (b * f - c * e) * iDet, 0],
        [(f * g - d * k) * iDet, (a * k - c * g) * iDet,
         (c * d - a * f) * iDet, 0],
        [(d * h - e * g) * iDet, (g * b - a * h) * iDet,
         (a * e - b * d) * iDet, 0]
      ];
      var lastRow = [];
      for (var i = 0; i < 3; i++) {
        var val = 0;
        for (var j = 0; j < 3; j++) {
          val += m[3][j] * Ainv[j][i];
        }
        lastRow.push(val);
      }
      lastRow.push(1);
      Ainv.push(lastRow);
      return Ainv;
    }

    function transposeMatrix4(m) {
      return [[m[0][0], m[1][0], m[2][0], m[3][0]],
              [m[0][1], m[1][1], m[2][1], m[3][1]],
              [m[0][2], m[1][2], m[2][2], m[3][2]],
              [m[0][3], m[1][3], m[2][3], m[3][3]]];
    }

    function multVecMatrix(v, m) {
      var result = [];
      for (var i = 0; i < 4; i++) {
        var val = 0;
        for (var j = 0; j < 4; j++) {
          val += v[j] * m[j][i];
        }
        result.push(val);
      }
      return result;
    }

    function normalize(v) {
      var len = length(v);
      return [v[0] / len, v[1] / len, v[2] / len];
    }

    function length(v) {
      return Math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
    }

    function combine(v1, v2, v1s, v2s) {
      return [v1s * v1[0] + v2s * v2[0], v1s * v1[1] + v2s * v2[1],
              v1s * v1[2] + v2s * v2[2]];
    }

    function cross(v1, v2) {
      return [v1[1] * v2[2] - v1[2] * v2[1],
              v1[2] * v2[0] - v1[0] * v2[2],
              v1[0] * v2[1] - v1[1] * v2[0]];
    }

    // TODO: Implement 2D matrix decomposition.
    // http://dev.w3.org/csswg/css-transforms/#decomposing-a-2d-matrix
    function decomposeMatrix(matrix) {
      var m3d = [
        matrix.slice(0, 4),
        matrix.slice(4, 8),
        matrix.slice(8, 12),
        matrix.slice(12, 16)
      ];

      // skip normalization step as m3d[3][3] should always be 1
      if (m3d[3][3] !== 1) {
        return null;
      }

      var perspectiveMatrix = [];
      for (var i = 0; i < 4; i++) {
        perspectiveMatrix.push(m3d[i].slice());
      }

      for (var i = 0; i < 3; i++) {
        perspectiveMatrix[i][3] = 0;
      }

      if (determinant(perspectiveMatrix) === 0) {
        return false;
      }

      var rhs = [];

      var perspective;
      if (m3d[0][3] || m3d[1][3] || m3d[2][3]) {
        rhs.push(m3d[0][3]);
        rhs.push(m3d[1][3]);
        rhs.push(m3d[2][3]);
        rhs.push(m3d[3][3]);

        var inversePerspectiveMatrix = inverse(perspectiveMatrix);
        var transposedInversePerspectiveMatrix =
            transposeMatrix4(inversePerspectiveMatrix);
        perspective = multVecMatrix(rhs, transposedInversePerspectiveMatrix);
      } else {
        perspective = [0, 0, 0, 1];
      }

      var translate = m3d[3].slice(0, 3);

      var row = [];
      row.push(m3d[0].slice(0, 3));
      var scale = [];
      scale.push(length(row[0]));
      row[0] = normalize(row[0]);

      var skew = [];
      row.push(m3d[1].slice(0, 3));
      skew.push(dot(row[0], row[1]));
      row[1] = combine(row[1], row[0], 1.0, -skew[0]);

      scale.push(length(row[1]));
      row[1] = normalize(row[1]);
      skew[0] /= scale[1];

      row.push(m3d[2].slice(0, 3));
      skew.push(dot(row[0], row[2]));
      row[2] = combine(row[2], row[0], 1.0, -skew[1]);
      skew.push(dot(row[1], row[2]));
      row[2] = combine(row[2], row[1], 1.0, -skew[2]);

      scale.push(length(row[2]));
      row[2] = normalize(row[2]);
      skew[1] /= scale[2];
      skew[2] /= scale[2];

      var pdum3 = cross(row[1], row[2]);
      if (dot(row[0], pdum3) < 0) {
        for (var i = 0; i < 3; i++) {
          scale[i] *= -1;
          row[i][0] *= -1;
          row[i][1] *= -1;
          row[i][2] *= -1;
        }
      }

      var t = row[0][0] + row[1][1] + row[2][2] + 1;
      var s;
      var quaternion;

      if (t > 1e-4) {
        s = 0.5 / Math.sqrt(t);
        quaternion = [
          (row[2][1] - row[1][2]) * s,
          (row[0][2] - row[2][0]) * s,
          (row[1][0] - row[0][1]) * s,
          0.25 / s
        ];
      } else if (row[0][0] > row[1][1] && row[0][0] > row[2][2]) {
        s = Math.sqrt(1 + row[0][0] - row[1][1] - row[2][2]) * 2.0;
        quaternion = [
          0.25 * s,
          (row[0][1] + row[1][0]) / s,
          (row[0][2] + row[2][0]) / s,
          (row[2][1] - row[1][2]) / s
        ];
      } else if (row[1][1] > row[2][2]) {
        s = Math.sqrt(1.0 + row[1][1] - row[0][0] - row[2][2]) * 2.0;
        quaternion = [
          (row[0][1] + row[1][0]) / s,
          0.25 * s,
          (row[1][2] + row[2][1]) / s,
          (row[0][2] - row[2][0]) / s
        ];
      } else {
        s = Math.sqrt(1.0 + row[2][2] - row[0][0] - row[1][1]) * 2.0;
        quaternion = [
          (row[0][2] + row[2][0]) / s,
          (row[1][2] + row[2][1]) / s,
          0.25 * s,
          (row[1][0] - row[0][1]) / s
        ];
      }

      return [translate, scale, skew, quaternion, perspective];
    }
    return decomposeMatrix;
  })();

  function dot(v1, v2) {
    var result = 0;
    for (var i = 0; i < v1.length; i++) {
      result += v1[i] * v2[i];
    }
    return result;
  }

  function multiplyMatrices(a, b) {
    return [
      a[0] * b[0] + a[4] * b[1] + a[8] * b[2] + a[12] * b[3],
      a[1] * b[0] + a[5] * b[1] + a[9] * b[2] + a[13] * b[3],
      a[2] * b[0] + a[6] * b[1] + a[10] * b[2] + a[14] * b[3],
      a[3] * b[0] + a[7] * b[1] + a[11] * b[2] + a[15] * b[3],

      a[0] * b[4] + a[4] * b[5] + a[8] * b[6] + a[12] * b[7],
      a[1] * b[4] + a[5] * b[5] + a[9] * b[6] + a[13] * b[7],
      a[2] * b[4] + a[6] * b[5] + a[10] * b[6] + a[14] * b[7],
      a[3] * b[4] + a[7] * b[5] + a[11] * b[6] + a[15] * b[7],

      a[0] * b[8] + a[4] * b[9] + a[8] * b[10] + a[12] * b[11],
      a[1] * b[8] + a[5] * b[9] + a[9] * b[10] + a[13] * b[11],
      a[2] * b[8] + a[6] * b[9] + a[10] * b[10] + a[14] * b[11],
      a[3] * b[8] + a[7] * b[9] + a[11] * b[10] + a[15] * b[11],

      a[0] * b[12] + a[4] * b[13] + a[8] * b[14] + a[12] * b[15],
      a[1] * b[12] + a[5] * b[13] + a[9] * b[14] + a[13] * b[15],
      a[2] * b[12] + a[6] * b[13] + a[10] * b[14] + a[14] * b[15],
      a[3] * b[12] + a[7] * b[13] + a[11] * b[14] + a[15] * b[15]
    ];
  }

  // TODO: This can probably be made smaller.
  function convertItemToMatrix(item) {
    switch (item.t) {
      // TODO: Handle units other than rads and degs.
      case 'rotatex':
        var rads = item.d[0].rad || 0;
        var degs = item.d[0].deg || 0;
        var angle = (degs * Math.PI / 180) + rads;
        return [1, 0, 0, 0,
                0, Math.cos(angle), Math.sin(angle), 0,
                0, -Math.sin(angle), Math.cos(angle), 0,
                0, 0, 0, 1];
      case 'rotatey':
        var rads = item.d[0].rad || 0;
        var degs = item.d[0].deg || 0;
        var angle = (degs * Math.PI / 180) + rads;
        return [Math.cos(angle), 0, -Math.sin(angle), 0,
                0, 1, 0, 0,
                Math.sin(angle), 0, Math.cos(angle), 0,
                0, 0, 0, 1];
      case 'rotate':
      case 'rotatez':
        var rads = item.d[0].rad || 0;
        var degs = item.d[0].deg || 0;
        var angle = (degs * Math.PI / 180) + rads;
        return [Math.cos(angle), Math.sin(angle), 0, 0,
                -Math.sin(angle), Math.cos(angle), 0, 0,
                0, 0, 1, 0,
                0, 0, 0, 1];
      case 'rotate3d':
        var x = item.d[0];
        var y = item.d[1];
        var z = item.d[2];
        var rads = item.d[3].rad || 0;
        var degs = item.d[3].deg || 0;
        var angle = (degs * Math.PI / 180) + rads;

        var sqrLength = x * x + y * y + z * z;
        if (sqrLength === 0) {
          x = 1;
          y = 0;
          z = 0;
        } else if (sqrLength !== 1) {
          var length = Math.sqrt(sqrLength);
          x /= length;
          y /= length;
          z /= length;
        }

        var s = Math.sin(angle / 2);
        var sc = s * Math.cos(angle / 2);
        var sq = s * s;
        return [
          1 - 2 * (y * y + z * z) * sq,
          2 * (x * y * sq + z * sc),
          2 * (x * z * sq - y * sc),
          0,

          2 * (x * y * sq - z * sc),
          1 - 2 * (x * x + z * z) * sq,
          2 * (y * z * sq + x * sc),
          0,

          2 * (x * z * sq + y * sc),
          2 * (y * z * sq - x * sc),
          1 - 2 * (x * x + y * y) * sq,
          0,

          0, 0, 0, 1
        ];
      case 'scale':
        return [item.d[0], 0, 0, 0,
                0, item.d[1], 0, 0,
                0, 0, 1, 0,
                0, 0, 0, 1];
      case 'scalex':
        return [item.d[0], 0, 0, 0,
                0, 1, 0, 0,
                0, 0, 1, 0,
                0, 0, 0, 1];
      case 'scaley':
        return [1, 0, 0, 0,
                0, item.d[0], 0, 0,
                0, 0, 1, 0,
                0, 0, 0, 1];
      case 'scalez':
        return [1, 0, 0, 0,
                0, 1, 0, 0,
                0, 0, item.d[0], 0,
                0, 0, 0, 1];
      case 'scale3d':
        return [item.d[0], 0, 0, 0,
                0, item.d[1], 0, 0,
                0, 0, item.d[2], 0,
                0, 0, 0, 1];
      // FIXME: Skew behaves differently in Blink, FireFox and here. Need to work out why.
      case 'skew':
        var xDegs = item.d[0].deg || 0;
        var xRads = item.d[0].rad || 0;
        var yDegs = item.d[1].deg || 0;
        var yRads = item.d[1].rad || 0;
        var xAngle = (xDegs * Math.PI / 180) + xRads;
        var yAngle = (yDegs * Math.PI / 180) + yRads;
        return [1, Math.tan(yAngle), 0, 0,
                Math.tan(xAngle), 1, 0, 0,
                0, 0, 1, 0,
                0, 0, 0, 1];
      case 'skewx':
        var rads = item.d[0].rad || 0;
        var degs = item.d[0].deg || 0;
        var angle = (degs * Math.PI / 180) + rads;
        return [1, 0, 0, 0,
                Math.tan(angle), 1, 0, 0,
                0, 0, 1, 0,
                0, 0, 0, 1];
      case 'skewy':
        var rads = item.d[0].rad || 0;
        var degs = item.d[0].deg || 0;
        var angle = (degs * Math.PI / 180) + rads;
        return [1, Math.tan(angle), 0, 0,
                0, 1, 0, 0,
                0, 0, 1, 0,
                0, 0, 0, 1];
      // TODO: Work out what to do with non-px values.
      case 'translate':
        var x = item.d[0].px || 0;
        var y = item.d[1].px || 0;
        return [1, 0, 0, 0,
                0, 1, 0, 0,
                0, 0, 1, 0,
                x, y, 0, 1];
      case 'translatex':
        var x = item.d[0].px || 0;
        return [1, 0, 0, 0,
                0, 1, 0, 0,
                0, 0, 1, 0,
                x, 0, 0, 1];
      case 'translatey':
        var y = item.d[0].px || 0;
        return [1, 0, 0, 0,
                0, 1, 0, 0,
                0, 0, 1, 0,
                0, y, 0, 1];
      case 'translatez':
        var z = item.d[0].px || 0;
        return [1, 0, 0, 0,
                0, 1, 0, 0,
                0, 0, 1, 0,
                0, 0, z, 1];
      case 'translate3d':
        var x = item.d[0].px || 0;
        var y = item.d[1].px || 0;
        var z = item.d[2].px || 0;
        return [1, 0, 0, 0,
                0, 1, 0, 0,
                0, 0, 1, 0,
                x, y, z, 1];
      case 'perspective':
        var p = item.d[0].px ? (-1 / item.d[0].px) : 0;
        return [
          1, 0, 0, 0,
          0, 1, 0, 0,
          0, 0, 1, p,
          0, 0, 0, 1];
      case 'matrix':
        return [item.d[0], item.d[1], 0, 0,
                item.d[2], item.d[3], 0, 0,
                0, 0, 1, 0,
                item.d[4], item.d[5], 0, 1];
      case 'matrix3d':
        return item.d;
      default:
        WEB_ANIMATIONS_TESTING && console.assert(false, 'Transform item type ' + item.t +
            ' conversion to matrix not yet implemented.');
    }
  }

  function convertToMatrix(transformList) {
    if (transformList.length === 0) {
      return [1, 0, 0, 0,
              0, 1, 0, 0,
              0, 0, 1, 0,
              0, 0, 0, 1];
    }
    return transformList.map(convertItemToMatrix).reduce(multiplyMatrices);
  }

  function makeMatrixDecomposition(transformList) {
    return [decomposeMatrix(convertToMatrix(transformList))];
  }

  scope.dot = dot;
  scope.makeMatrixDecomposition = makeMatrixDecomposition;

})(webAnimations1, webAnimationsTesting);
