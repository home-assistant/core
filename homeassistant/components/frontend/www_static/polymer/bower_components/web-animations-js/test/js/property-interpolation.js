suite('property-interpolation', function() {
  test('unmatched inputs return step interpolation', function() {
    tests = [['unknown', 'input', 'tuple'],
             ['unknown', '10px', '50px'],
             ['width', '100px', 'auto'],
             ['width', 'auto', '100px']];
    for (var i = 0; i < tests.length; i++) {
      var property = tests[i][0];
      var left = tests[i][1];
      var right = tests[i][2];
      interpolation = webAnimations1.propertyInterpolation(property, left, right);
      assert.equal(interpolation(-1), left);
      assert.equal(interpolation(0), left);
      assert.equal(interpolation(0.45), left);
      assert.equal(interpolation(0.5), right);
      assert.equal(interpolation(0.55), right);
      assert.equal(interpolation(1), right);
      assert.equal(interpolation(2), right);
    }
  });

  test('registers camel cased property names', function() {
    function merge(a, b) {
      return [a, b, function(x) { return a + b; }];
    };
    webAnimations1.addPropertiesHandler(Number, merge, ['dummy-property']);
    assert.equal(webAnimations1.propertyInterpolation('dummy-property', 1, 2)(0.5), 3);
    assert.equal(webAnimations1.propertyInterpolation('dummyProperty', 5, 3)(0.5), 8);
  });
});
