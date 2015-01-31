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

  var styleAttributes = {
    cssText: 1,
    length: 1,
    parentRule: 1,
  };

  var styleMethods = {
    getPropertyCSSValue: 1,
    getPropertyPriority: 1,
    getPropertyValue: 1,
    item: 1,
    removeProperty: 1,
    setProperty: 1,
  };

  var styleMutatingMethods = {
    removeProperty: 1,
    setProperty: 1,
  };

  function configureProperty(object, property, descriptor) {
    descriptor.enumerable = true;
    descriptor.configurable = true;
    Object.defineProperty(object, property, descriptor);
  }

  function AnimatedCSSStyleDeclaration(element) {
    WEB_ANIMATIONS_TESTING && console.assert(!(element.style instanceof AnimatedCSSStyleDeclaration),
        'Element must not already have an animated style attached.');

    // Stores the inline style of the element on its behalf while the
    // polyfill uses the element's inline style to simulate web animations.
    // This is needed to fake regular inline style CSSOM access on the element.
    this._surrogateStyle = document.createElementNS('http://www.w3.org/1999/xhtml', 'div').style;
    this._style = element.style;
    this._length = 0;
    this._isAnimatedProperty = {};

    // Copy the inline style contents over to the surrogate.
    for (var i = 0; i < this._style.length; i++) {
      var property = this._style[i];
      this._surrogateStyle[property] = this._style[property];
    }
    this._updateIndices();
  }

  AnimatedCSSStyleDeclaration.prototype = {
    get cssText() {
      return this._surrogateStyle.cssText;
    },
    set cssText(text) {
      var isAffectedProperty = {};
      for (var i = 0; i < this._surrogateStyle.length; i++) {
        isAffectedProperty[this._surrogateStyle[i]] = true;
      }
      this._surrogateStyle.cssText = text;
      this._updateIndices();
      for (var i = 0; i < this._surrogateStyle.length; i++) {
        isAffectedProperty[this._surrogateStyle[i]] = true;
      }
      for (var property in isAffectedProperty) {
        if (!this._isAnimatedProperty[property]) {
          this._style.setProperty(property, this._surrogateStyle.getPropertyValue(property));
        }
      }
    },
    get length() {
      return this._surrogateStyle.length;
    },
    get parentRule() {
      return this._style.parentRule;
    },
    // Mirror the indexed getters and setters of the surrogate style.
    _updateIndices: function() {
      while (this._length < this._surrogateStyle.length) {
        Object.defineProperty(this, this._length, {
          configurable: true,
          enumerable: false,
          get: (function(index) {
            return function() { return this._surrogateStyle[index]; };
          })(this._length)
        });
        this._length++;
      }
      while (this._length > this._surrogateStyle.length) {
        this._length--;
        Object.defineProperty(this, this._length, {
          configurable: true,
          enumerable: false,
          value: undefined
        });
      }
    },
    _set: function(property, value) {
      this._style[property] = value;
      this._isAnimatedProperty[property] = true;
    },
    _clear: function(property) {
      this._style[property] = this._surrogateStyle[property];
      delete this._isAnimatedProperty[property];
    },
  };

  // Wrap the style methods.
  for (var method in styleMethods) {
    AnimatedCSSStyleDeclaration.prototype[method] = (function(method, modifiesStyle) {
      return function() {
        var result = this._surrogateStyle[method].apply(this._surrogateStyle, arguments);
        if (modifiesStyle) {
          if (!this._isAnimatedProperty[arguments[0]])
            this._style[method].apply(this._style, arguments);
          this._updateIndices();
        }
        return result;
      }
    })(method, method in styleMutatingMethods);
  }

  // Wrap the style.cssProperty getters and setters.
  for (var property in document.documentElement.style) {
    if (property in styleAttributes || property in styleMethods) {
      continue;
    }
    (function(property) {
      configureProperty(AnimatedCSSStyleDeclaration.prototype, property, {
        get: function() {
          return this._surrogateStyle[property];
        },
        set: function(value) {
          this._surrogateStyle[property] = value;
          this._updateIndices();
          if (!this._isAnimatedProperty[property])
            this._style[property] = value;
        }
      });
    })(property);
  }

  function ensureStyleIsPatched(element) {
    if (element._webAnimationsPatchedStyle)
      return;

    var animatedStyle = new AnimatedCSSStyleDeclaration(element);
    try {
      configureProperty(element, 'style', { get: function() { return animatedStyle; } });
    } catch (_) {
      // iOS and older versions of Safari (pre v7) do not support overriding an element's
      // style object. Animations will clobber any inline styles as a result.
      element.style._set = function(property, value) {
        element.style[property] = value;
      };
      element.style._clear = function(property) {
        element.style[property] = '';
      };
    }

    // We must keep a handle on the patched style to prevent it from getting GC'd.
    element._webAnimationsPatchedStyle = element.style;
  }

  scope.apply = function(element, property, value) {
    ensureStyleIsPatched(element);
    element.style._set(scope.propertyName(property), value);
  };

  scope.clear = function(element, property) {
    if (element._webAnimationsPatchedStyle) {
      element.style._clear(scope.propertyName(property));
    }
  };

  if (WEB_ANIMATIONS_TESTING)
    testing.ensureStyleIsPatched = ensureStyleIsPatched;

})(webAnimations1, webAnimationsTesting);
