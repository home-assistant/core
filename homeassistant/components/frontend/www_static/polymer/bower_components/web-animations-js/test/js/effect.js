
function leftAsNumber(target) {
  var left = getComputedStyle(target).left;
  return Number(left.substring(0, left.length - 2));
}

suite('effect', function() {
  // Test normalize.
  test('Normalize keyframes with all offsets specified but not sorted by offset. Some offsets are out of [0, 1] range.', function() {
    var normalizedKeyframes;
    assert.throws(function() {
      normalizedKeyframes = normalizeKeyframes([
        {offset: 0},
        {offset: -1},
        {offset: 1},
        {offset: 0.5},
        {offset: 2}
      ]);
    });
  });

  test('Normalize keyframes with some offsets not specified, and not sorted by offset.', function() {
    assert.throws(function() {
      normalizeKeyframes([
        {offset: 0.5},
        {offset: 0},
        {offset: 0.8},
        {},
        {offset: 1}
      ]);
    });
  });

  test('Normalize keyframes with some offsets not specified, and not sorted by offset. Out of order keyframes are out of [0, 1] range.', function() {
    assert.throws(function() {
      normalizeKeyframes([
        {offset: 0},
        {offset: -1},
        {offset: 0.5},
        {},
        {offset: 1}
      ]);
    });
  });

  test('Normalize keyframes with some offsets not specified, but sorted by offset where specified. Some offsets are out of [0, 1] range.', function() {
    var normalizedKeyframes;
    assert.doesNotThrow(function() {
      normalizedKeyframes = normalizeKeyframes([
        {offset: -1},
        {offset: 0},
        {offset: 0.5},
        {},
        {},
        {offset: 2}
      ]);
    });
    assert.equal(normalizedKeyframes.length, 4);
    assert.closeTo(normalizedKeyframes[0].offset, 0, 0.001);
    assert.closeTo(normalizedKeyframes[1].offset, 0.5, 0.001);
    assert.closeTo(normalizedKeyframes[2].offset, 0.75, 0.001);
    assert.closeTo(normalizedKeyframes[3].offset, 1, 0.001);
  });

  test('Normalize keyframes with some offsets not specified, but sorted by offset where specified. All specified offsets in [0, 1] range.', function() {
    var normalizedKeyframes;
    assert.doesNotThrow(function() {
      normalizedKeyframes = normalizeKeyframes([
        {left: '0px', offset: 0},
        {left: '10px'},
        {left: '20px'},
        {left: '30px', offset: 0.6},
        {left: '40px'},
        {left: '50px'}
      ]);
    });
    assert.equal(normalizedKeyframes.length, 6);
    assert.closeTo(normalizedKeyframes[0].offset, 0, 0.001);
    assert.equal(normalizedKeyframes[0].left, '0px');
    assert.closeTo(normalizedKeyframes[1].offset, 0.2, 0.001);
    assert.equal(normalizedKeyframes[1].left, '10px');
    assert.closeTo(normalizedKeyframes[2].offset, 0.4, 0.001);
    assert.equal(normalizedKeyframes[2].left, '20px');
    assert.closeTo(normalizedKeyframes[3].offset, 0.6, 0.001);
    assert.equal(normalizedKeyframes[3].left, '30px');
    assert.closeTo(normalizedKeyframes[4].offset, 0.8, 0.001);
    assert.equal(normalizedKeyframes[4].left, '40px');
    assert.closeTo(normalizedKeyframes[5].offset, 1, 0.001);
    assert.equal(normalizedKeyframes[5].left, '50px');
  });

  test('Normalize keyframes with no offsets specified.', function() {
    var normalizedKeyframes;
    assert.doesNotThrow(function() {
      normalizedKeyframes = normalizeKeyframes([
        {left: '0px'},
        {left: '10px'},
        {left: '20px'},
        {left: '30px'},
        {left: '40px'}
      ]);
    });
    assert.equal(normalizedKeyframes.length, 5);
    assert.closeTo(normalizedKeyframes[0].offset, 0, 0.001);
    assert.equal(normalizedKeyframes[0].left, '0px');
    assert.closeTo(normalizedKeyframes[1].offset, 0.25, 0.001);
    assert.equal(normalizedKeyframes[1].left, '10px');
    assert.closeTo(normalizedKeyframes[2].offset, 0.5, 0.001);
    assert.equal(normalizedKeyframes[2].left, '20px');
    assert.closeTo(normalizedKeyframes[3].offset, 0.75, 0.001);
    assert.equal(normalizedKeyframes[3].left, '30px');
    assert.closeTo(normalizedKeyframes[4].offset, 1, 0.001);
    assert.equal(normalizedKeyframes[4].left, '40px');
  });

  test('Normalize keyframes where a keyframe has an offset that is not a number.', function() {
    assert.throws(function() {
      normalizeKeyframes([
        {offset: 0},
        {offset: 'one'},
        {offset: 1}
      ]);
    });
  });

  test('Normalize keyframes where a keyframe has an offset that is a numeric string.', function() {
    var normalizedKeyframes;
    assert.doesNotThrow(function() {
      normalizedKeyframes = normalizeKeyframes([
        {offset: 0},
        {offset: '0.5'},
        {offset: 1}
      ]);
    });
    assert.equal(normalizedKeyframes.length, 3);
    assert.closeTo(normalizedKeyframes[0].offset, 0, 0.001);
    assert.closeTo(normalizedKeyframes[1].offset, 0.5, 0.001);
    assert.closeTo(normalizedKeyframes[2].offset, 1, 0.001);
  });

  test('Normalize keyframes where some keyframes have easings.', function() {
    var normalizedKeyframes;
    assert.doesNotThrow(function() {
      normalizedKeyframes = normalizeKeyframes([
        {left: '0px', easing: 'ease-in'},
        {left: '10px'},
        {left: '0px'}
      ]);
    });
  });

  test('Normalize keyframes with invalid specified easing.', function() {
    var normalizedKeyframes;
    assert.doesNotThrow(function() {
      normalizedKeyframes = normalizeKeyframes([
        {left: '0px', easing: 'easy-peasy'},
        {left: '10px'},
        {left: '0px'}
      ]);
    });
    assert.equal('' + normalizedKeyframes[0].easing, 'function (x) { return x; }');
  });

  test('Normalize keyframes where some properties are given non-string, non-number values.', function() {
    var normalizedKeyframes;
    assert.doesNotThrow(function() {
      normalizedKeyframes = normalizeKeyframes([
        {left: {}},
        {left: '100px'},
        {left: []}
      ]);
    });
    assert(normalizedKeyframes.length, 3);
    assert.equal(normalizedKeyframes[0].left, '[object Object]');
    assert.equal(normalizedKeyframes[1].left, '100px');
    assert.equal(normalizedKeyframes[2].left, '');
  });

  test('Normalize input that is not an array.', function() {
    assert.throws(function() {
      normalizeKeyframes(10);
    });
  });

  test('Normalize an empty array.', function() {
    var normalizedKeyframes;
    assert.doesNotThrow(function() {
      normalizedKeyframes = normalizeKeyframes([]);
    });
    assert.deepEqual(normalizedKeyframes, []);
  });

  test('Normalize null.', function() {
    var normalizedKeyframes;
    assert.doesNotThrow(function() {
      normalizedKeyframes = normalizeKeyframes(null);
    });
    assert.deepEqual(normalizedKeyframes, []);
  });

  test('Normalize shorthands.', function() {
    var normalizedKeyframes;
    assert.doesNotThrow(function() {
      normalizedKeyframes = normalizeKeyframes([{borderColor: 'purple green orange blue'}, {borderColor: 'red'}]);
    });
    assert.equal(normalizedKeyframes[0].borderTopColor, 'purple');
    assert.equal(normalizedKeyframes[0].borderRightColor, 'green');
    assert.equal(normalizedKeyframes[0].borderBottomColor, 'orange');
    assert.equal(normalizedKeyframes[0].borderLeftColor, 'blue');
    assert.equal(normalizedKeyframes[1].borderTopColor, 'red');
    assert.equal(normalizedKeyframes[1].borderRightColor, 'red');
    assert.equal(normalizedKeyframes[1].borderBottomColor, 'red');
    assert.equal(normalizedKeyframes[1].borderLeftColor, 'red');

    assert.doesNotThrow(function() {
      normalizedKeyframes = normalizeKeyframes([{font: 'italic bold 20pt / 200% serif'}, {font: 'italic normal bold 50pt serif'}]);
    });
    assert.equal(normalizedKeyframes[0].fontStyle, 'italic');
    assert.equal(normalizedKeyframes[0].fontVariant, 'normal');
    assert.equal(normalizedKeyframes[0].fontWeight, '700');
    assert.equal(normalizedKeyframes[0].fontSize, '20pt');
    assert.equal(normalizedKeyframes[0].lineHeight, '200%');
    assert.equal(normalizedKeyframes[0].fontFamily, 'serif');
    assert.equal(normalizedKeyframes[1].fontStyle, 'italic');
    assert.equal(normalizedKeyframes[1].fontVariant, 'normal');
    assert.equal(normalizedKeyframes[1].fontWeight, '700');
    assert.equal(normalizedKeyframes[1].fontSize, '50pt');
    assert.equal(normalizedKeyframes[1].lineHeight, 'normal');
    assert.equal(normalizedKeyframes[1].fontFamily, 'serif');
  });

  // Test makePropertySpecificKeyframeGroups.
  test('Make property specific keyframe groups for a simple effect with one property.', function() {
    var groups;
    assert.doesNotThrow(function() {
      groups = makePropertySpecificKeyframeGroups(normalizeKeyframes([
        {left: '0px'},
        {left: '200px', offset: 0.3},
        {left: '0px'}
      ]));
    });
    assert.equal(Object.getOwnPropertyNames(groups).length, 1);
    assert.equal(groups.left.length, 3);
    assert.closeTo(groups.left[0].offset, 0, 0.001);
    assert.equal(groups.left[0].value, '0px');
    assert.closeTo(groups.left[1].offset, 0.3, 0.001);
    assert.equal(groups.left[1].value, '200px');
    assert.closeTo(groups.left[2].offset, 1, 0.001);
    assert.equal(groups.left[2].value, '0px');
  });

  test('Make property specific keyframe groups for an effect with three properties.', function() {
    var groups;
    assert.doesNotThrow(function() {
      groups = makePropertySpecificKeyframeGroups(normalizeKeyframes([
        {left: '0px', top: '200px', opacity: 1},
        {left: '200px', top: '0px'},
        {left: '0px', top: '200px', opacity: 0},
        {top: '0px', opacity: 1},
        {left: '200px', top: '200px', opacity: 0}
      ]));
    });
    assert.equal(Object.getOwnPropertyNames(groups).length, 3);

    assert.equal(groups.left.length, 4);
    assert.closeTo(groups.left[0].offset, 0, 0.001);
    assert.equal(groups.left[0].value, '0px');
    assert.closeTo(groups.left[1].offset, 0.25, 0.001);
    assert.equal(groups.left[1].value, '200px');
    assert.closeTo(groups.left[2].offset, 0.5, 0.001);
    assert.equal(groups.left[2].value, '0px');
    assert.closeTo(groups.left[3].offset, 1, 0.001);
    assert.equal(groups.left[3].value, '200px');

    assert.equal(groups.top.length, 5);
    assert.closeTo(groups.top[0].offset, 0, 0.001);
    assert.equal(groups.top[0].value, '200px');
    assert.closeTo(groups.top[1].offset, 0.25, 0.001);
    assert.equal(groups.top[1].value, '0px');
    assert.closeTo(groups.top[2].offset, 0.5, 0.001);
    assert.equal(groups.top[2].value, '200px');
    assert.closeTo(groups.top[3].offset, 0.75, 0.001);
    assert.equal(groups.top[3].value, '0px');
    assert.closeTo(groups.top[4].offset, 1, 0.001);
    assert.equal(groups.top[4].value, '200px');

    assert.equal(groups.opacity.length, 4);
    assert.closeTo(groups.opacity[0].offset, 0, 0.001);
    assert.equal(groups.opacity[0].value, 1);
    assert.closeTo(groups.opacity[1].offset, 0.5, 0.001);
    assert.equal(groups.opacity[1].value, 0);
    assert.closeTo(groups.opacity[2].offset, 0.75, 0.001);
    assert.equal(groups.opacity[2].value, 1);
    assert.closeTo(groups.opacity[3].offset, 1, 0.001);
    assert.equal(groups.opacity[3].value, 0);
  });

  test('Make property specific keyframes when the offset of the last keyframe is specified but not equal to 1.', function() {
    assert.throws(function() {
      makePropertySpecificKeyframeGroups(normalizeKeyframes([
        {left: '0px', offset: 0},
        {left: '20px'},
        {left: '30px', offset: 0.9}
      ]));
    });
  });

  test('Make property specific keyframes when no properties are animated, and the offset of the last keyframe is specified but not equal to 1.', function() {
    var groups;
    assert.doesNotThrow(function() {
      groups = makePropertySpecificKeyframeGroups(normalizeKeyframes([
        {offset: 0},
        {},
        {offset: 0.9}
      ]));
    });
    assert.equal(Object.getOwnPropertyNames(groups).length, 0);
  });

  test('Make property specific keyframes when a property appears in some keyframes, but not in the last keyframe.', function() {
    assert.throws(function() {
      makePropertySpecificKeyframeGroups(normalizeKeyframes([
        {left: '0px', top: '0px'},
        {left: '10px', top: '10px'},
        {top: '20px'}
      ]));
    });
  });

  test('Make property specific keyframes when a property appears in some keyframes, but not in the first keyframe.', function() {
    assert.throws(function() {
      makePropertySpecificKeyframeGroups(normalizeKeyframes([
        {left: '0px'},
        {left: '10px', top: '10px'},
        {left: '20px', top: '20px'}
      ]));
    });
  });

  test('Make property specific keyframes where two properties are animated. One property in a keyframe with offset 1. One property in the last keyframe, with no offset.', function() {
    var groups;
    assert.doesNotThrow(function() {
      groups = makePropertySpecificKeyframeGroups(normalizeKeyframes([
        {left: '0px', top: '0px', offset: 0},
        {left: '20px', offset: 1},
        {top: '20px'}
      ]));
    });
    assert.equal(Object.getOwnPropertyNames(groups).length, 2);
  });

  test('Make property specific keyframes where two properties are animated. One property in a keyframe with offset 0. One property in the first keyframe, with no offset.', function() {
    var groups;
    assert.doesNotThrow(function() {
      groups = makePropertySpecificKeyframeGroups(normalizeKeyframes([
        {top: '0px'},
        {left: '0px', offset: 0},
        {left: '20px', top: '20px', offset: 1}
      ]));
    });
    assert.equal(Object.getOwnPropertyNames(groups).length, 2);
  });

  // Test per-keyframe easings.
  test('Apply keyframe easings.', function() {
    var target1 = document.createElement('div');
    var target2 = document.createElement('div');
    target1.style.position = 'absolute';
    target2.style.position = 'absolute';
    document.body.appendChild(target1);
    document.body.appendChild(target2);

    var player1 = target1.animate(
        [
          {left: '0px'},
          {left: '50px', offset: 0.25},
          {left: '0px'}
        ],
        {duration: 4000, fill: 'forwards'});
    var player2 = target2.animate(
        [
          {left: '0px', easing: 'ease-in'},
          {left: '50px', offset: 0.25},
          {left: '0px'}
        ],
        {duration: 4000, fill: 'forwards'});

    tick(0);
    assert.equal(leftAsNumber(target1), 0);
    assert.equal(leftAsNumber(target2), 0);
    tick(250);
    assert.closeTo(leftAsNumber(target1), 12.5, 1);
    assert.closeTo(leftAsNumber(target2), 4.65, 1);
    tick(500);
    assert.closeTo(leftAsNumber(target1), 25, 1);
    assert.closeTo(leftAsNumber(target2), 15.25, 1);
    tick(1000);
    assert.equal(leftAsNumber(target1), 50);
    assert.equal(leftAsNumber(target2), 50);

    tick(2500);
    assert.equal(leftAsNumber(target1), 25);
    assert.equal(leftAsNumber(target2), 25);
    tick(4000);
    assert.equal(leftAsNumber(target1), 0);
    assert.equal(leftAsNumber(target2), 0);
  });

  // Test makeInterpolations.
  test('Make interpolations for a simple effect with one property.', function() {
    var interpolations;
    assert.doesNotThrow(function() {
      interpolations = makeInterpolations(makePropertySpecificKeyframeGroups(normalizeKeyframes([
        {left: '0px'},
        {left: '200px', offset: 0.3},
        {left: '0px'}
      ])));
    });
    assert.equal(interpolations.length, 2);

    assert.closeTo(interpolations[0].startTime, 0, 0.001);
    assert.closeTo(interpolations[0].endTime, 0.3, 0.001);
    assert.equal(interpolations[0].property, 'left');
    assert.equal(typeof interpolations[0].interpolation, 'function');

    assert.closeTo(interpolations[1].startTime, 0.3, 0.001);
    assert.closeTo(interpolations[1].endTime, 1, 0.001);
    assert.equal(interpolations[1].property, 'left');
    assert.equal(typeof interpolations[1].interpolation, 'function');
  });
});

suite('effect-convertEffectInput', function() {
  setup(function() {
    this.target = document.createElement('div');
    this.target.style.position = 'absolute';
    document.documentElement.appendChild(this.target);
  });
  teardown(function() {
    if (this.target.parent)
      this.target.removeChild(this.target);
  });

  test('Convert effect input for a simple effect with one property.', function() {
    var effectFunction;
    assert.doesNotThrow(function() {
      effectFunction = webAnimations1.convertEffectInput([
        {left: '0px'},
        {left: '200px', offset: 0.3},
        {left: '100px'}
      ]);
    });

    effectFunction(this.target, 0);
    assert.closeTo(leftAsNumber(this.target), 0, 0.001);
    effectFunction(this.target, 0.075);
    assert.closeTo(leftAsNumber(this.target), 50, 0.001);
    effectFunction(this.target, 0.15);
    assert.closeTo(leftAsNumber(this.target), 100, 0.001);
    effectFunction(this.target, 0.65);
    assert.closeTo(leftAsNumber(this.target), 150, 0.001);
    effectFunction(this.target, 1);
    assert.closeTo(leftAsNumber(this.target), 100, 0.001);
    effectFunction(this.target, 2);
    assert.closeTo(leftAsNumber(this.target), -42.856, 0.01);
  });

  test('Convert effect input where one property is animated and the property has two keyframes at offset 1.', function() {
    var effectFunction;
    assert.doesNotThrow(function() {
      effectFunction = webAnimations1.convertEffectInput([
        {left: '0px', offset: 0},
        {left: '20px', offset: 1},
        {left: '30px'}
      ]);
    });
    effectFunction(this.target, 1);
    assert.equal(getComputedStyle(this.target).left, '30px');
    effectFunction(this.target, 2);
    assert.equal(getComputedStyle(this.target).left, '30px');
  });

  test('Convert effect input and apply effect at fraction null.', function() {
    var effectFunction;
    var underlying = getComputedStyle(this.target).left;
    assert.doesNotThrow(function() {
      effectFunction = webAnimations1.convertEffectInput([
        {left: '0px'},
        {left: '100px'}
      ]);
    });

    effectFunction(this.target, 1);
    assert.equal(getComputedStyle(this.target).left, '100px');
    effectFunction(this.target, null);
    assert.equal(getComputedStyle(this.target).left, underlying);
  });
});
