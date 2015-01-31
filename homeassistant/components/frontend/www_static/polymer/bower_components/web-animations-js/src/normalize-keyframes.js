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

(function(shared, testing) {
  var shorthandToLonghand = {
    background: [
      'backgroundImage',
      'backgroundPosition',
      'backgroundSize',
      'backgroundRepeat',
      'backgroundAttachment',
      'backgroundOrigin',
      'backgroundClip',
      'backgroundColor'
    ],
    border: [
      'borderTopColor',
      'borderTopStyle',
      'borderTopWidth',
      'borderRightColor',
      'borderRightStyle',
      'borderRightWidth',
      'borderBottomColor',
      'borderBottomStyle',
      'borderBottomWidth',
      'borderLeftColor',
      'borderLeftStyle',
      'borderLeftWidth'
    ],
    borderBottom: [
      'borderBottomWidth',
      'borderBottomStyle',
      'borderBottomColor'
    ],
    borderColor: [
      'borderTopColor',
      'borderRightColor',
      'borderBottomColor',
      'borderLeftColor'
    ],
    borderLeft: [
      'borderLeftWidth',
      'borderLeftStyle',
      'borderLeftColor'
    ],
    borderRadius: [
      'borderTopLeftRadius',
      'borderTopRightRadius',
      'borderBottomRightRadius',
      'borderBottomLeftRadius'
    ],
    borderRight: [
      'borderRightWidth',
      'borderRightStyle',
      'borderRightColor'
    ],
    borderTop: [
      'borderTopWidth',
      'borderTopStyle',
      'borderTopColor'
    ],
    borderWidth: [
      'borderTopWidth',
      'borderRightWidth',
      'borderBottomWidth',
      'borderLeftWidth'
    ],
    flex: [
      'flexGrow',
      'flexShrink',
      'flexBasis'
    ],
    font: [
      'fontFamily',
      'fontSize',
      'fontStyle',
      'fontVariant',
      'fontWeight',
      'lineHeight'
    ],
    margin: [
      'marginTop',
      'marginRight',
      'marginBottom',
      'marginLeft'
    ],
    outline: [
      'outlineColor',
      'outlineStyle',
      'outlineWidth'
    ],
    padding: [
      'paddingTop',
      'paddingRight',
      'paddingBottom',
      'paddingLeft'
    ]
  };

  var shorthandExpanderElem = document.createElementNS('http://www.w3.org/1999/xhtml', 'div');

  var borderWidthAliases = {
    thin: '1px',
    medium: '3px',
    thick: '5px'
  };

  var aliases = {
    borderBottomWidth: borderWidthAliases,
    borderLeftWidth: borderWidthAliases,
    borderRightWidth: borderWidthAliases,
    borderTopWidth: borderWidthAliases,
    fontSize: {
      'xx-small': '60%',
      'x-small': '75%',
      'small': '89%',
      'medium': '100%',
      'large': '120%',
      'x-large': '150%',
      'xx-large': '200%'
    },
    fontWeight: {
      normal: '400',
      bold: '700'
    },
    outlineWidth: borderWidthAliases,
    textShadow: {
      none: '0px 0px 0px transparent'
    },
    boxShadow: {
      none: '0px 0px 0px 0px transparent'
    }
  };

  function antiAlias(property, value) {
    if (property in aliases) {
      return aliases[property][value] || value;
    }
    return value;
  }

  // This delegates parsing shorthand value syntax to the browser.
  function expandShorthandAndAntiAlias(property, value, result) {
    var longProperties = shorthandToLonghand[property];
    if (longProperties) {
      shorthandExpanderElem.style[property] = value;
      for (var i in longProperties) {
        var longProperty = longProperties[i];
        var longhandValue = shorthandExpanderElem.style[longProperty];
        result[longProperty] = antiAlias(longProperty, longhandValue);
      }
    } else {
      result[property] = antiAlias(property, value);
    }
  };

  function normalizeKeyframes(effectInput) {
    if (!Array.isArray(effectInput) && effectInput !== null)
      throw new TypeError('Keyframe effect must be null or an array of keyframes');

    if (effectInput == null)
      return [];

    var keyframeEffect = effectInput.map(function(originalKeyframe) {
      var keyframe = {};
      for (var member in originalKeyframe) {
        var memberValue = originalKeyframe[member];
        if (member == 'offset') {
          if (memberValue != null) {
            memberValue = Number(memberValue);
            if (!isFinite(memberValue))
              throw new TypeError('keyframe offsets must be numbers.');
          }
        } else if (member == 'composite') {
          throw {
            type: DOMException.NOT_SUPPORTED_ERR,
            name: 'NotSupportedError',
            message: 'add compositing is not supported'
          };
        } else if (member == 'easing') {
          memberValue = shared.toTimingFunction(memberValue);
        } else {
          memberValue = '' + memberValue;
        }
        expandShorthandAndAntiAlias(member, memberValue, keyframe);
      }
      if (keyframe.offset == undefined)
        keyframe.offset = null;
      if (keyframe.easing == undefined)
        keyframe.easing = shared.toTimingFunction('linear');
      return keyframe;
    });

    var everyFrameHasOffset = true;
    var looselySortedByOffset = true;
    var previousOffset = -Infinity;
    for (var i = 0; i < keyframeEffect.length; i++) {
      var offset = keyframeEffect[i].offset;
      if (offset != null) {
        if (offset < previousOffset) {
          throw {
            code: DOMException.INVALID_MODIFICATION_ERR,
            name: 'InvalidModificationError',
            message: 'Keyframes are not loosely sorted by offset. Sort or specify offsets.'
          };
        }
        previousOffset = offset;
      } else {
        everyFrameHasOffset = false;
      }
    }

    keyframeEffect = keyframeEffect.filter(function(keyframe) {
      return keyframe.offset >= 0 && keyframe.offset <= 1;
    });

    function spaceKeyframes() {
      var length = keyframeEffect.length;
      if (keyframeEffect[length - 1].offset == null)
        keyframeEffect[length - 1].offset = 1;
      if (length > 1 && keyframeEffect[0].offset == null)
        keyframeEffect[0].offset = 0;

      var previousIndex = 0;
      var previousOffset = keyframeEffect[0].offset;
      for (var i = 1; i < length; i++) {
        var offset = keyframeEffect[i].offset;
        if (offset != null) {
          for (var j = 1; j < i - previousIndex; j++)
            keyframeEffect[previousIndex + j].offset = previousOffset + (offset - previousOffset) * j / (i - previousIndex);
          previousIndex = i;
          previousOffset = offset;
        }
      }
    }
    if (!everyFrameHasOffset)
      spaceKeyframes();

    return keyframeEffect;
  }

  shared.normalizeKeyframes = normalizeKeyframes;

  if (WEB_ANIMATIONS_TESTING) {
    testing.normalizeKeyframes = normalizeKeyframes;
  }

})(webAnimationsShared, webAnimationsTesting);
