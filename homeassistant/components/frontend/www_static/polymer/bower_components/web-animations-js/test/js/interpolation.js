suite('interpolation', function() {
  test('interpolate numbers', function() {
    assert.equal(interpolate(4, 2, 0.2), 3.6);
  });
  test('interpolate bools', function() {
    assert.equal(interpolate(false, true, 0.4), false);
    assert.equal(interpolate(false, true, 0.5), true);
    assert.equal(interpolate(false, true, 0.5), true);
  });
  test('interpolate lists', function() {
    assert.deepEqual(interpolate([1, 2, 3], [4, 5, 6], 0.5), [2.5, 3.5, 4.5]);
    assert.deepEqual(interpolate([1], [4], 0.6), [2.8]);
    assert.deepEqual(interpolate([false], [true], 0.6), [true]);
    assert.deepEqual(interpolate([1, false, [3, 6]], [4, true, [6, 8]], 0.6), [2.8, true, [4.8, 7.2]]);
  });
});
