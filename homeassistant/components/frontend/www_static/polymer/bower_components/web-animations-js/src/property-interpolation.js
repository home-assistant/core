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

  var propertyHandlers = {};

  function addPropertyHandler(parser, merger, property) {
    propertyHandlers[property] = propertyHandlers[property] || [];
    propertyHandlers[property].push([parser, merger]);
  }
  function addPropertiesHandler(parser, merger, properties) {
    for (var i = 0; i < properties.length; i++) {
      var property = properties[i];
      WEB_ANIMATIONS_TESTING && console.assert(property.toLowerCase() === property);
      addPropertyHandler(parser, merger, property);
      if (/-/.test(property)) {
        // Add camel cased variant.
        addPropertyHandler(parser, merger, property.replace(/-(.)/g, function(_, c) {
          return c.toUpperCase();
        }));
      }
    }
  }
  scope.addPropertiesHandler = addPropertiesHandler;

  function propertyInterpolation(property, left, right) {
    var handlers = left == right ? [] : propertyHandlers[property];
    for (var i = 0; handlers && i < handlers.length; i++) {
      var parsedLeft = handlers[i][0](left);
      var parsedRight = handlers[i][0](right);
      if (parsedLeft !== undefined && parsedRight !== undefined) {
        var interpolationArgs = handlers[i][1](parsedLeft, parsedRight);
        if (interpolationArgs) {
          var interp = scope.Interpolation.apply(null, interpolationArgs);
          return function(t) {
            if (t == 0) return left;
            if (t == 1) return right;
            return interp(t);
          };
        }
      }
    }
    return scope.Interpolation(false, true, function(bool) {
      return bool ? right : left;
    });
  }
  scope.propertyInterpolation = propertyInterpolation;

})(webAnimations1, webAnimationsTesting);

