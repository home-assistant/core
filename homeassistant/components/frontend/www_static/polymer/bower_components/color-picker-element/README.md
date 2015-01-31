# &lt;color-picker&gt;

A custom HTML element that provides a color picker.  

## Demo
[See demo](http://bbrewer97202.github.io/color-picker-element/demo/index.html)

## Requirements
No extra requirements if run in a browser that supports custom elements, shadow DOM and HTML imports.  Otherwise, use the platform.js polyfill provided.

## Install

Install the component using [Bower](http://bower.io/):

```sh
$ bower install color-picker-element --save
```

## Usage

1. Import Web Components' polyfill:

    ```html
    <script src="bower_components/platform/platform.js"></script>
    ```

2. Import Custom Element:

    ```html
    <link rel="import" href="bower_components/color-picker-element/dist/color-picker.html">
    ```

3. Embed on page, optionally providing width and height attributes

    ```html
    <color-picker width="200" height="200"></color-picker>
    ```

## Development

1. Install local dependencies (requires [Bower](http://bower.io/)):

    ```sh
    $ bower install && npm install
    ```

3. Start the watch task and development server, then open `http://localhost:8000/demo` in your browser.

    ```sh
    $ gulp
    ```

## License

[MIT License](http://opensource.org/licenses/MIT)
