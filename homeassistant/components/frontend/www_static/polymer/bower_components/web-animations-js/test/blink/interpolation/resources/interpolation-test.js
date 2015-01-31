/*
 * Copyright (C) 2013 Google Inc. All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are
 * met:
 *
 *     * Redistributions of source code must retain the above copyright
 * notice, this list of conditions and the following disclaimer.
 *     * Redistributions in binary form must reproduce the above
 * copyright notice, this list of conditions and the following disclaimer
 * in the documentation and/or other materials provided with the
 * distribution.
 *     * Neither the name of Google Inc. nor the names of its
 * contributors may be used to endorse or promote products derived from
 * this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 * "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 * LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
 * A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
 * OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
 * SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
 * LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
 * DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
 * THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 * (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
 * OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

/*
 * This script is intended to be used for constructing layout tests which
 * exercise the interpolation functionaltiy of the animation system.
 * Tests which run using this script should be portable across browsers.
 *
 * The following function is exported:
 *  * assertInterpolation({property: x, from: y, to: z}, [{at: fraction, is: value}])
 *    Constructs a test case which for each fraction will output a PASS
 *    or FAIL depending on whether the interpolated result matches
 *    'value'. Replica elements are constructed to aid eyeballing test
 *    results.
 */
'use strict';
(function() {
  var endEvent = 'animationend';
  var testCount = 0;
  var animationEventCount = 0;
  var durationSeconds = 0;
  var iterationCount = 0.5;
  var delaySeconds = 0;
  var fragment = document.createDocumentFragment();
  var fragmentAttachedListeners = [];
  var style = document.createElement('style');
  var afterTestCallback = null;
  fragment.appendChild(style);

  var tests = document.createElement('div');
  tests.id = 'interpolation-tests';
  tests.textContent = 'Interpolation Tests:';
  fragment.appendChild(tests);

  var updateScheduled = false;
  function maybeScheduleUpdate() {
    if (updateScheduled) {
      return;
    }
    updateScheduled = true;
    setTimeout(function() {
      updateScheduled = false;
      document.body.appendChild(fragment);
      fragmentAttachedListeners.forEach(function(listener) {listener();});
    }, 0);
  }

  function evaluateTests() {
    var targets = document.querySelectorAll('.target.active');
    for (var i = 0; i < targets.length; i++) {
      targets[i].evaluate();
    }
  }

  function afterTest(callback) {
    afterTestCallback = callback;
  }

  // Constructs a timing function which produces 'y' at x = 0.5
  function createEasing(y) {
    // FIXME: if 'y' is > 0 and < 1 use a linear timing function and allow
    // 'x' to vary. Use a bezier only for values < 0 or > 1.
    if (y == 0) {
      return 'steps(1, end)';
    }
    if (y == 1) {
      return 'steps(1, start)';
    }
    if (y == 0.5) {
      return 'steps(2, end)';
    }
    // Approximate using a bezier.
    var b = (8 * y - 1) / 6;
    return 'cubic-bezier(0, ' + b + ', 1, ' + b + ')';
  }

  function createTestContainer(description, className) {
    var testContainer = document.createElement('div');
    testContainer.setAttribute('description', description);
    testContainer.classList.add('test');
    if (className) {
      testContainer.classList.add(className);
    }
    return testContainer;
  }

  function convertPropertyToCamelCase(property) {
    return property.replace(/^-/, '').replace(/-\w/g, function(m) {return m[1].toUpperCase();});
  }

  function describeTest(params) {
    return convertPropertyToCamelCase(params.property) + ': from [' + params.from + '] to [' + params.to + ']';
  }

  var nextKeyframeId = 0;
  function assertInterpolation(params, expectations) {
    var testId = 'test-' + ++nextKeyframeId;
    var nextCaseId = 0;
    var testContainer = createTestContainer(describeTest(params), testId);
    tests.appendChild(testContainer);
    expectations.forEach(function(expectation) {
        testContainer.appendChild(makeInterpolationTest(
            expectation.at, testId, 'case-' + ++nextCaseId, params, expectation.is));
    });
    maybeScheduleUpdate();
  }

  function roundNumbers(value) {
    // Round numbers to two decimal places.
    return value.replace(/-?\d*\.\d+/g, function(n) {
        return (parseFloat(n).toFixed(2)).
            replace(/\.\d+/, function(m) {
              return m.replace(/0+$/, '');
            }).
            replace(/\.$/, '').
            replace(/^-0$/, '0');
      });
  }

  function normalizeValue(value) {
    return roundNumbers(value).
        // Place whitespace between tokens.
        replace(/([\w\d.]+|[^\s])/g, '$1 ').
        replace(/\s+/g, ' ');
  }

  function createTargetContainer(id) {
    var targetContainer = document.createElement('div');
    var template = document.querySelector('#target-template');
    if (template) {
      if (template.content)
        targetContainer.appendChild(template.content.cloneNode(true));
      else if (template.querySelector('div'))
        targetContainer.appendChild(template.querySelector('div').cloneNode(true));
      else
        targetContainer.appendChild(template.cloneNode(true));
      // Remove whitespace text nodes at start / end.
      while (targetContainer.firstChild.nodeType != Node.ELEMENT_NODE && !/\S/.test(targetContainer.firstChild.nodeValue)) {
        targetContainer.removeChild(targetContainer.firstChild);
      }
      while (targetContainer.lastChild.nodeType != Node.ELEMENT_NODE && !/\S/.test(targetContainer.lastChild.nodeValue)) {
        targetContainer.removeChild(targetContainer.lastChild);
      }
      // If the template contains just one element, use that rather than a wrapper div.
      if (targetContainer.children.length == 1 && targetContainer.childNodes.length == 1) {
        targetContainer = targetContainer.firstChild;
        targetContainer.parentNode.removeChild(targetContainer);
      }
    }
    var target = targetContainer.querySelector('.target') || targetContainer;
    target.classList.add('target');
    target.classList.add(id);
    return targetContainer;
  }

  function sanitizeUrls(value) {
    var matches = value.match(/url\([^\)]*\)/g);
    if (matches !== null) {
      for (var i = 0; i < matches.length; ++i) {
        var url = /url\(([^\)]*)\)/g.exec(matches[i])[1];
        var anchor = document.createElement('a');
        anchor.href = url;
        anchor.pathname = '...' + anchor.pathname.substring(anchor.pathname.lastIndexOf('/'));
        value = value.replace(matches[i], 'url(' + anchor.href + ')');
      }
    }
    return value;
  }

  function makeInterpolationTest(fraction, testId, caseId, params, expectation) {
    var t = async_test(describeTest(params) + ' at ' + fraction);
    var targetContainer = createTargetContainer(caseId);
    var target = targetContainer.querySelector('.target') || targetContainer;
    target.classList.add('active');
    var replicaContainer, replica;
    replicaContainer = createTargetContainer(caseId);
    replica = replicaContainer.querySelector('.target') || replicaContainer;
    replica.classList.add('replica');
    replica.style.setProperty(params.property, expectation);
    if (params.prefixedProperty) {
      for (var i = 0; i < params.prefixedProperty.length; i++) {
        replica.style.setProperty(params.prefixedProperty[i], expectation);
      }
    }

    target.evaluate = function() {
      var target = this;
      t.step(function() {
        window.CSS && assert_true(CSS.supports(params.property, expectation));
        var value = getComputedStyle(target).getPropertyValue(params.property);
        var property = params.property;
        if (params.prefixedProperty) {
          var i = 0;
          while (i < params.prefixedProperty.length && !value) {
            property = params.prefixedProperty[i++];
            value = getComputedStyle(target).getPropertyValue(property)
          }
        }
        if (!value) {
          assert_false(params.property + ' not supported by this browser');
        }
        var originalValue = value;
        var parsedExpectation = getComputedStyle(replica).getPropertyValue(property);
        assert_equals(normalizeValue(originalValue), normalizeValue(parsedExpectation));
        t.done();
      });
    };

    var easing = createEasing(fraction);
    testCount++;
    var keyframes = [{}, {}];
    keyframes[0][convertPropertyToCamelCase(params.property)] = params.from;
    keyframes[1][convertPropertyToCamelCase(params.property)] = params.to;
    fragmentAttachedListeners.push(function() {
      target.animate(keyframes, {
          fill: 'forwards',
          duration: 1,
          easing: easing,
          delay: -0.5,
          iterations: 0.5,
        });
      animationEnded();
    });
    var testFragment = document.createDocumentFragment();
    testFragment.appendChild(targetContainer);
    replica && testFragment.appendChild(replicaContainer);
    testFragment.appendChild(document.createTextNode('\n'));
    return testFragment;
  }

  var finished = false;
  function finishTest() {
    finished = true;
    evaluateTests();
    if (afterTestCallback) {
      afterTestCallback();
    }
    if (window.testRunner) {
      var results = document.querySelector('#results');
      document.documentElement.textContent = '';
      document.documentElement.appendChild(results);
      testRunner.dumpAsText();
      testRunner.notifyDone();
    }
  }

  if (window.testRunner) {
    testRunner.waitUntilDone();
  }

  function isLastAnimationEvent() {
    return !finished && animationEventCount === testCount;
  }

  function animationEnded() {
    animationEventCount++;
    if (!isLastAnimationEvent()) {
      return;
    }
    finishTest();
  }

  document.documentElement.addEventListener(endEvent, animationEnded);

  if (!window.testRunner) {
    setTimeout(function() {
      if (finished) {
        return;
      }
      finishTest();
    }, 10000);
  }

  window.assertInterpolation = assertInterpolation;
  window.afterTest = afterTest;
})();
