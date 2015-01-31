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

(function() {
  var assert = chai.assert;
  mocha.setup({ ui: 'tdd' });

  var iframe;
  function defineTestharnessTest(shouldPass, testFile) {
    var name = shouldPass ? testFile : 'Expected Failure: ' + testFile;
    test(name, function(done) {
      window.initTestHarness = function(child) {
        child.add_completion_callback(function(tests, harness_status) {
          var failures = tests.filter(function(result) {
            return result.status != 0;
          }).map(function(failure) {
            return failure.name + ':\n' + failure.message;
          });
          var error;
          if (shouldPass && failures.length) {
            error = new Error('\n' + failures.join('\n\n'));
            error.stack = null;
          } else if (!shouldPass && failures.length == 0) {
            error = new Error('\nExpected to fail, but passed');
            error.stack = null;
          }
          done(error);
        });
      };
      iframe.src = testFile;
    });
  }

  suite('testharness tests', function() {
    setup(function() {
      iframe = document.createElement('iframe');
      document.body.appendChild(iframe);
    });
    teardown(function() {
      iframe.parentNode.removeChild(iframe);
    });
    testHarnessTests.forEach(defineTestharnessTest.bind(null, true));
    testHarnessFailures.forEach(defineTestharnessTest.bind(null, false));
  });

  suite('interpolation tests', function() {
    setup(function() {
      iframe = document.createElement('iframe');
      document.body.appendChild(iframe);
    });
    teardown(function() {
      iframe.parentNode.removeChild(iframe);
    });
    interpolationTests.forEach(defineTestharnessTest.bind(null, true));
    interpolationFailures.forEach(defineTestharnessTest.bind(null, false));
  });

  addEventListener('load', function() {
    mocha.run();
  });
})();
