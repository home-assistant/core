(function(){
'use strict'

function createElement() {
  var element = document.createElement('div');
  element.style.position = 'absolute';
  document.documentElement.appendChild(element);
  return element;
}

function heldTiming(progress) {
  return {
    duration: 1000,
    fill: 'forwards',
    delay: -progress * 1000,
  };
}

function assertAnimationStyles(keyframes, expectations, description) {
  for (var progress in expectations) {
    var element = createElement();
    element.animate(keyframes, heldTiming(progress));

    var computedStyle = getComputedStyle(element);
    for (var property in expectations[progress]) {
      assert_equals(computedStyle[property], expectations[progress][property],
          property + ' at ' + (progress * 100) + '%' + (description ? ' ' + description : ''));
    }
  }
}

window.assertAnimationStyles = assertAnimationStyles;
})();
