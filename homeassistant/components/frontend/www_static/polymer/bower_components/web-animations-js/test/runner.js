var WEB_ANIMATIONS_TESTING = true;
var webAnimationsTesting = window;
var assert = chai.assert;
mocha.setup({ ui: 'tdd' });

function loadWebAnimationsBuildTarget(target) {
  var config = webAnimationsTargetConfig[target];
  config.src.concat(config.test).forEach(function(file) {
    document.write('<script src="../' + file + '"></script>\n');
  });
}

(function() {

  var pageError = null;

  addEventListener('error', function(event) {
    pageError = event.filename + ':' + event.lineno + ' ' + event.message;
  });

  addEventListener('load', function() {

    // Inject test suite for page errors if any encountered.
    if (pageError) {
      suite('page-script-errors', function() {
        test('no script errors on page', function() {
          assert.fail(null, null, pageError);
        });
      });
    }

    mocha.run();
  });

})();
