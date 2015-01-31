(function() {

  var scopeSrc = [
      'src/scope.js'];

  var webAnimations1Src = [
      'src/animation-node.js',
      'src/effect.js',
      'src/property-interpolation.js',
      'src/animation.js',
      'src/apply-preserving-inline-style.js',
      'src/element-animatable.js',
      'src/interpolation.js',
      'src/matrix-interpolation.js',
      'src/player.js',
      'src/tick.js',
      'src/matrix-decomposition.js',
      'src/handler-utils.js',
      'src/shadow-handler.js',
      'src/number-handler.js',
      'src/visibility-handler.js',
      'src/color-handler.js',
      'src/dimension-handler.js',
      'src/box-handler.js',
      'src/transform-handler.js',
      'src/font-weight-handler.js',
      'src/position-handler.js',
      'src/shape-handler.js',
      'src/property-names.js',
  ];

  var liteWebAnimations1Src = [
      'src/animation-node.js',
      'src/effect.js',
      'src/property-interpolation.js',
      'src/animation.js',
      'src/apply.js',
      'src/element-animatable.js',
      'src/interpolation.js',
      'src/player.js',
      'src/tick.js',
      'src/handler-utils.js',
      'src/shadow-handler.js',
      'src/number-handler.js',
      'src/visibility-handler.js',
      'src/color-handler.js',
      'src/dimension-handler.js',
      'src/box-handler.js',
      'src/transform-handler.js',
      'src/property-names.js',
  ];


  var sharedSrc = [
      'src/timing-utilities.js',
      'src/normalize-keyframes.js',
      'src/deprecation.js',
  ];

  var webAnimationsNextSrc = [
      'src/timeline.js',
      'src/web-animations-next-player.js',
      'src/animation-constructor.js',
      'src/effect-callback.js',
      'src/group-constructors.js'];

  var webAnimations1Test = [
      'test/js/animation-node.js',
      'test/js/apply-preserving-inline-style.js',
      'test/js/box-handler.js',
      'test/js/color-handler.js',
      'test/js/dimension-handler.js',
      'test/js/effect.js',
      'test/js/interpolation.js',
      'test/js/matrix-interpolation.js',
      'test/js/number-handler.js',
      'test/js/player.js',
      'test/js/player-finish-event.js',
      'test/js/property-interpolation.js',
      'test/js/tick.js',
      'test/js/timing.js',
      'test/js/transform-handler.js'];

  var webAnimationsNextTest = webAnimations1Test.concat(
      'test/js/animation-constructor.js',
      'test/js/effect-callback.js',
      'test/js/group-constructors.js',
      'test/js/group-player.js',
      'test/js/group-player-finish-event.js',
      'test/js/timeline.js');

  // This object specifies the source and test files for different Web Animation build targets.
  var targetConfig = {
    'web-animations': {
      scopeSrc: scopeSrc,
      sharedSrc: sharedSrc,
      webAnimations1Src: webAnimations1Src,
      webAnimationsNextSrc: [],
      src: scopeSrc.concat(sharedSrc).concat(webAnimations1Src),
      test: webAnimations1Test,
    },
    'web-animations-next': {
      scopeSrc: scopeSrc,
      sharedSrc: sharedSrc,
      webAnimations1Src: webAnimations1Src,
      webAnimationsNextSrc: webAnimationsNextSrc,
      src: scopeSrc.concat(sharedSrc).concat(webAnimations1Src).concat(webAnimationsNextSrc),
      test: webAnimationsNextTest,
    },
    'web-animations-next-lite': {
      scopeSrc: scopeSrc,
      sharedSrc: sharedSrc,
      webAnimations1Src: liteWebAnimations1Src,
      webAnimationsNextSrc: webAnimationsNextSrc,
      src: scopeSrc.concat(sharedSrc).concat(liteWebAnimations1Src).concat(webAnimationsNextSrc),
      test: [],
    },
  };

  if (typeof module != 'undefined')
    module.exports = targetConfig;
  else
    window.webAnimationsTargetConfig = targetConfig;
})();
