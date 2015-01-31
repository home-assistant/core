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

(function(scope, testing) {

  var aliased = {};

  function alias(name, aliases) {
    aliases.concat([name]).forEach(function(candidate) {
      if (candidate in document.documentElement.style) {
        aliased[name] = candidate;
      }
    });
  }
  alias('transform', ['webkitTransform', 'msTransform']);
  alias('transformOrigin', ['webkitTransformOrigin']);
  alias('perspective', ['webkitPerspective']);
  alias('perspectiveOrigin', ['webkitPerspectiveOrigin']);

  scope.propertyName = function(property) {
    return aliased[property] || property;
  };

})(webAnimations1, webAnimationsTesting);
