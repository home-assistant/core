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
  function parse(string) {
    var out = Number(string);
    if (isNaN(out) || out < 100 || out > 900 || out % 100 !== 0) {
      return;
    }
    return out;
  }

  function toCss(value) {
    value = Math.round(value / 100) * 100;
    value = scope.clamp(100, 900, value);
    if (value === 400) {
      return 'normal';
    }
    if (value === 700) {
      return 'bold';
    }
    return String(value);
  }

  function merge(left, right) {
    return [left, right, toCss];
  }

  scope.addPropertiesHandler(parse, merge, ['font-weight']);

})(webAnimations1);
