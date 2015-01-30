
Quick Start
-----------

To provide native Chrome Web Animation features (`Element.animate` and Playback
Control) in other browsers, use `web-animations.min.js`. To explore all of the
proposed Web Animations API, use `web-animations-next.min.js`.

What is Web Animations?
-----------------------

Web Animations is a new JavaScript API for driving animated content on the web.
By unifying the animation features of SVG and CSS, Web Animations unlocks
features previously only usable declaratively, and exposes powerful,
high-performance animation capabilities to developers.

For more details see the
[W3C specification](http://w3c.github.io/web-animations/).

What is the polyfill?
---------------------

The polyfill is a JavaScript implementation of the Web Animations API. It works
on modern versions of all major browsers. For more details about browser
support see <https://www.polymer-project.org/resources/compatibility.html>.

Getting Started
---------------

Here's a simple example of an animation that scales and changes the opacity of
a `<div>` over 0.5 seconds. The animation alternates producing a pulsing
effect.

    <script src="web-animations.min.js"></script>
    <div class="pulse" style="width:150px;">Hello world!</div>
    <script>
        var elem = document.querySelector('.pulse');
        var player = elem.animate([
            {opacity: 0.5, transform: "scale(0.5)"},
            {opacity: 1.0, transform: "scale(1)"}
        ], {
            direction: 'alternate',
            duration: 500,
            iterations: Infinity
        });
    </script>

Web Animations supports off-main-thread animations, and also allows procedural
generation of animations and fine-grained control of animation playback. See
<http://web-animations.github.io> for ideas and inspiration!

Native Fallback
---------------

When the polyfill runs on a browser that implements Element.animate and
AnimationPlayer Playback Control it will detect and use the underlying native
features.

Different Build Targets
-----------------------

### web-animations.min.js

Tracks the Web Animations features that are supported natively in browsers.
Today that means Element.animate and Playback Control in Chrome. If you’re not
sure what features you will need, start with this.

### web-animations-next.min.js

Contains all of web-animations.min.js plus features that are still undergoing
discussion or have yet to be implemented natively.

### web-animations-next-lite.min.js

A cut down version of web-animations-next, it removes several lesser used
property handlers and some of the larger and less used features such as matrix
interpolation/decomposition.

### Build Target Comparison

|                        | web-animations | web-animations-next | web-animations-next-lite |
|------------------------|:--------------:|:-------------------:|:------------------------:|
|Size (gzipped)          | 12.5kb         | 14kb                | 10.5kb                   |
|Element.animate         | ✔             | ✔                  | ✔                       |
|Timing input (easings, duration, fillMode, etc.) for animations| ✔ | ✔ | ✔             | 
|Playback control        | ✔             | ✔                  | ✔                       |
|Support for animating lengths, transforms and opacity| ✔ | ✔ | ✔                       |
|Support for Animating other CSS properties| ✔ | ✔            | 🚫                       |
|Matrix fallback for transform animations | ✔ | ✔             | 🚫                       |
|Animation constructor   | 🚫             | ✔                  | ✔                       |
|Simple Groups           | 🚫             | ✔                  | ✔                       |
|Custom Effects          | 🚫             | ✔                  | ✔                       |
|Timing input (easings, duration, fillMode, etc.) for groups</div>| 🚫 | 🚫\* | 🚫         |
|Additive animation      | 🚫             | 🚫\*                | 🚫                       |
|Motion path             | 🚫\*           | 🚫\*                | 🚫                       |
|Modifiable animation timing| 🚫          | 🚫\*                | 🚫\*                     |
|Modifiable group timing | 🚫             | 🚫\*                | 🚫\*                     |
|Usable inline style\*\* | ✔             | ✔                  | 🚫                       |

\* support is planned for these features.
\*\* see inline style caveat below.

Caveats
-------

Some things won’t ever be faithful to the native implementation due to browser
and CSS API limitations. These include:

### Inline Style

Inline style modification is the mechanism used by the polyfill to animate
properties. Both web-animations and web-animations-next incorporate a module
that emulates a vanilla inline style object, so that style modification from
JavaScript can still work in the presence of animations. However, to keep the
size of web-animations-next-lite as small as possible, the style emulation
module is not included. When using this version of the polyfill, JavaScript
inline style modification will be overwritten by animations.
Due to browser constraints inline style modification is not supported on iOS 7
or Safari 6 (or earlier versions).

### Prefix handling

The polyfill will automatically detect the correctly prefixed name to use when
writing animated properties back to the platform. Where possible, the polyfill
will only accept unprefixed versions of experimental features. For example:

    var animation = new Animation(elem, {"transform": "translate(100px, 100px)"}, 2000);

will work in all browsers that implement a conforming version of transform, but

    var animation = new Animation(elem, {"-webkit-transform": "translate(100px, 100px)"}, 2000);

will not work anywhere.

API and Specification Feedback
------------------------------

File an issue on GitHub: <https://github.com/w3c/web-animations/issues/new>.
Alternatively, send an email to <public-fx@w3.org> with subject line
“[web-animations] … message topic …”
([archives](http://lists.w3.org/Archives/Public/public-fx/)).

Polyfill Issues
---------------

Report any issues with this implementation on GitHub:
<https://github.com/web-animations/web-animations-next/issues/new>.

Breaking changes
----------------

When we make a potentially breaking change to the polyfill's API
surface (like a rename) where possible we will continue supporting the
old version, deprecated, for three months, and ensure that there are
console warnings to indicate that a change is pending. After three
months, the old version of the API surface (e.g. the old version of a
function name) will be removed. *If you see deprecation warnings you
can't avoid it by not updating*.

We also announce anything that isn't a bug fix on
[web-animations-changes@googlegroups.com](https://groups.google.com/forum/#!forum/web-animations-changes).
