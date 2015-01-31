function activeElement() {
  return window.ShadowDOMPolyfill ? wrap(document.activeElement) : document.activeElement;
}

function assertNodeHasFocus(node) {
  assert.strictEqual(activeElement(), node);
}

function ensureFocus(node, callback) {
  fake.downOnNode(node);
  fake.upOnNode(node);
  waitFor(function() {
    assertNodeHasFocus(node);
  }, callback);
}