suite('transform-handler parsing', function() {
  test('parse skew values', function() {
    assert.deepEqual(parseTransform('skew(10deg) skew(12deg,45deg) skewX(0) skewY(1.5rad)'), [
      {t: 'skew', d: [{deg: 10}, {deg: 0}]},
      {t: 'skew', d: [{deg: 12}, {deg: 45}]},
      {t: 'skewx', d: [{deg: 0}]},
      {t: 'skewy', d: [{rad: 1.5}]}
    ]);
  });

  test('parse scale values', function() {
    assert.deepEqual(parseTransform('scale(-2) scale(3,-4) scaleX(5) scaleY(-1) scaleZ(-3)'), [
      {t: 'scale', d: [-2, -2]},
      {t: 'scale', d: [3, -4]},
      {t: 'scalex', d: [5]},
      {t: 'scaley', d: [-1]},
      {t: 'scalez', d: [-3]}
    ]);
    assert.deepEqual(parseTransform('scale3d(-2, 0, 7)'),
        [{t: 'scale3d', d: [-2, 0, 7]}]);
  });

  test('parse rotate values', function() {
    assert.deepEqual(parseTransform('rotate(10deg) rotateX(0) rotateY(1.5rad) rotateZ(50grad)'), [
      {t: 'rotate', d: [{deg: 10}]},
      {t: 'rotatex', d: [{deg: 0}]},
      {t: 'rotatey', d: [{rad: 1.5}]},
      {t: 'rotatez', d: [{grad: 50}]}
    ]);
  });

  test('parse translate values', function() {
    assert.deepEqual(parseTransform('translate(20%, 30px) translate(30em, 40%) translate(50vw) translate(0)'), [
      {t: 'translate', d: [{'%': 20}, {px: 30}]},
      {t: 'translate', d: [{em: 30}, {'%': 40}]},
      {t: 'translate', d: [{vw: 50}, {px: 0}]},
      {t: 'translate', d: [{px: 0}, {px: 0}]}
    ]);
    assert.deepEqual(parseTransform('translateX(10px) translateX(20%) translateX(0)'), [
      {t: 'translatex', d: [{px: 10}]},
      {t: 'translatex', d: [{'%': 20}]},
      {t: 'translatex', d: [{px: 0}]}
    ]);
    assert.deepEqual(parseTransform('translateY(10px) translateY(20%) translateY(0)'), [
      {t: 'translatey', d: [{px: 10}]},
      {t: 'translatey', d: [{'%': 20}]},
      {t: 'translatey', d: [{px: 0}]}
    ]);
    assert.deepEqual(parseTransform('translateZ(10px) translateZ(0)'), [
      {t: 'translatez', d: [{px: 10}]},
      {t: 'translatez', d: [{px: 0}]}
    ]);
    assert.deepEqual(parseTransform('translate3d(10px, 20px, 30px) translate3d(0, 40%, 0) translate3d(50%, 0, 60px)'), [
      {t: 'translate3d', d: [{px: 10}, {px: 20}, {px: 30}]},
      {t: 'translate3d', d: [{px: 0}, {'%': 40}, {px: 0}]},
      {t: 'translate3d', d: [{'%': 50}, {px: 0}, {px: 60}]}
    ]);
  });

  test('invalid transforms fail to parse', function() {
    assert.isUndefined(parseTransform('translate(10px'));
    assert.isUndefined(parseTransform('translate()'));
    assert.isUndefined(parseTransform('translatex()'));
    assert.isUndefined(parseTransform('translatex(5)'));
    assert.isUndefined(parseTransform('rotate(5)'));
    assert.isUndefined(parseTransform('skew(5)'));
    assert.isUndefined(parseTransform('scale(5px)'));
    assert.isUndefined(parseTransform('rotatex(5px)'));
  });
});

suite('transform-handler interpolation', function() {
  test('simple transform interpolations', function() {
    assert.equal(
        webAnimations1.propertyInterpolation(
            'transform',
            'translateX(10px)',
            'translateX(20px)')(0.2),
        'translatex(12px)');
    assert.equal(
        webAnimations1.propertyInterpolation(
            'transform',
            'translate(10px, 10px) rotate(20deg)',
            'translate(20px, 20px) rotate(90deg)')(0.2),
        'translate(12px,12px) rotate(34deg)');
    assert.equal(
        webAnimations1.propertyInterpolation(
            'transform',
            'translate(10px, 10em) rotate(20deg)',
            'translate(20em, 20px) rotate(90deg)')(0.5),
        'translate(calc(5px + 10em),calc(5em + 10px)) rotate(55deg)');
    assert.equal(
        webAnimations1.propertyInterpolation(
            'transform',
            'rotateY(1000deg)',
            'rotateY(3000deg)')(0.4),
        'rotatey(1800deg)');
    assert.equal(
        webAnimations1.propertyInterpolation(
            'transform',
            'scale(6)',
            'scale(1,-4)')(0.2),
        'scale(5,4)');
    assert.equal(
        webAnimations1.propertyInterpolation(
            'transform',
            'skewX(5deg) translateY(5px)',
            'skewX(-35deg) translateY(45px)')(0.25),
        'skewx(-5deg) translatey(15px)');
  });

  test('transform interpolations with conversion to primitives', function() {
    assert.equal(
        webAnimations1.propertyInterpolation(
            'transform',
            'translateX(10px)',
            'translate(20px, 10px)')(0.2),
        'translate(12px,2px)');
    assert.equal(
        webAnimations1.propertyInterpolation(
            'transform',
            'translateX(10px)',
            'translateY(10px)')(0.2),
        'translate(8px,2px)');
    assert.equal(
        webAnimations1.propertyInterpolation(
            'transform',
            'translateX(10px)',
            'translateZ(10px)')(0.2),
        'translate3d(8px,0px,2px)');
    assert.equal(
        webAnimations1.propertyInterpolation(
            'transform',
            'scaleX(6)',
            'scale(1,6)')(0.2),
        'scale(5,2)');
    assert.equal(
        webAnimations1.propertyInterpolation(
            'transform',
            'skew(10deg)',
            'skewY(30deg)')(0.2),
        'skew(8deg,6deg)');
  });

  test('transform interpolations with none', function() {
    assert.equal(
        webAnimations1.propertyInterpolation(
            'transform',
            'none',
            'scale(5) translateX(100px) rotate(1000deg)')(0.25),
        'scale(2,2) translatex(25px) rotate(250deg)');
    assert.equal(
        webAnimations1.propertyInterpolation(
            'transform',
            'scale(5) translateX(100px) rotate(1000deg)',
            'none')(0.75),
        'scale(2,2) translatex(25px) rotate(250deg)');
    assert.equal(
        webAnimations1.propertyInterpolation(
            'transform',
            'none',
            'scaleX(5) skewY(100grad)')(0.25),
        'scalex(2) skewy(25grad)');
    assert.equal(
        webAnimations1.propertyInterpolation(
            'transform',
            'none',
            'none')(0.4),
        'none');
  });
});
