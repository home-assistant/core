### 1.0.5 - *January 6 2015*

  * Fix loading the polyfill in an SVG document
  * Fix a problem where groups didn't take effect in their first frame
  * Don't rely on performance.now

### 1.0.4 - *December 8 2014*

  * Fix a critical bug where deprecation logic wasn't being loaded
    when `web-animations-next` and `web-animations-next-lite` were
    executed on top of a native `element.animate`.

### 1.0.3 - *December 4 2014*

  * Fix a critical bug on iOS 7 and Safari <= 6. Due to limitations,
    inline style patching is not supported on these platforms.

### 1.0.2 - *November 28 2014*

  * Deprecated `AnimationTiming.playbackRate`.

    For example, this is no longer supported:

        var player = element.animate(
            keyframes,
            {duration: 1000, playbackRate: 2});

    Use `AnimationPlayer.playbackRate` instead:

        var player = element.animate(
            keyframes,
            {duration: 1000});
        player.playbackRate = 2;

    If you have any feedback on this change, please start a discussion
    on the public-fx mailing list:
    http://lists.w3.org/Archives/Public/public-fx/

    Or file an issue against the specification on GitHub:
    https://github.com/w3c/web-animations/issues/new

### 1.0.1 - *November 26 2014*

  * Players should be constructed in idle state
  * `play()` and `reverse()` should not force a start times
  * Add `requestAnimationFrame` ids and `cancelAnimationFrame`

### 1.0.0 — *November 21 2014*

  The web-animations-js hackers are pleased to announce the release of
  a new codebase for the Web Animations Polyfill:
  https://github.com/web-animations/web-animations-js

  The previous polyfill has been moved to:
  https://github.com/web-animations/web-animations-js-legacy

  The new codebase is focused on code-size -- our smallest target is
  now only 33kb or 11kb after gzip.

  We've implemented native fallback. If the target browser provides
  Web Animations features natively, the Polyfill will use them.

  We now provide three different build targets:

  `web-animations.min.js` - Tracks the Web Animations features that
  are supported natively in browsers. Today that means Element.animate
  and Playback Control in Chrome. If you’re not sure what features you
  will need, start with this.

  `web-animations-next.min.js` - All of web-animations.min.js plus
  features that are still undergoing discussion or have yet to be
  implemented natively.

  `web-animations-next-lite.min.js` - A cut down version of
  web-animations-next, removes several lesser used property handlers
  and some of the larger and less used features such as matrix
  interpolation/decomposition.

  Not all features of the previous polyfill have been ported to the
  new codebase; most notably mutation of Animations and Groups and
  Additive Animations are not yet supported. These features are still
  important and will be implemented in the coming weeks.
