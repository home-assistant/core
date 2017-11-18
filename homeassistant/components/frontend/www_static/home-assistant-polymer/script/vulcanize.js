#!/usr/bin/env node

var Vulcanize = require('vulcanize');
var minify = require('html-minifier');
var hyd = require('hydrolysis');
var fs = require('fs');

if (!fs.existsSync('build')) {
  fs.mkdirSync('build');
}
if (!fs.existsSync('build/panels')) {
  fs.mkdirSync('build/panels');
}

function minifyHTML(html) {
  return minify.minify(html, {
    customAttrAssign: [/\$=/],
    removeComments: true,
    removeCommentsFromCDATA: true,
    removeCDATASectionsFromCDATA: true,
    collapseWhitespace: true,
    removeScriptTypeAttributes: true,
    removeStyleLinkTypeAttributes: true,
    minifyJS: true,
    minifyCSS: true,
  });
}

const baseVulcanOptions = {
  inlineScripts: true,
  inlineCss: true,
  implicitStrip: true,
  stripComments: true,
};

const panelVulcan = new Vulcanize({
  inlineScripts: true,
  inlineCss: true,
  implicitStrip: true,
  stripComments: true,
  stripExcludes: [
    'panels/hassio/hassio-main.html'
  ],
});

const baseExcludes = [
  'bower_components/font-roboto/roboto.html',
  'bower_components/paper-styles/color.html',
];

const toProcess = [
  // This is the main entry point
  {
    source: './src/home-assistant.html',
    output: './build/frontend.html',
    vulcan: new Vulcanize(Object.assign({}, baseVulcanOptions, {
      stripExcludes: baseExcludes,
    })),
  },
  // This is the Hass.io configuration panel
  // It's build standalone because it is embedded in the supervisor.
  {
    source: './panels/hassio/hassio-main.html',
    output: './build-temp/hassio-main.html',
    vulcan: new Vulcanize(Object.assign({}, baseVulcanOptions, {
      stripExcludes: baseExcludes.concat('bower_components/polymer/polymer.html'),
    })),
  },
];

fs.readdirSync('./panels').forEach((panel) => {
  toProcess.push({
    source: `./panels/${panel}/ha-panel-${panel}.html`,
    output: `./build/panels/ha-panel-${panel}.html`,
    vulcan: panelVulcan,
  });
});

function vulcanizeEntry(entry) {
  return new Promise((resolve, reject) => {
    console.log('Processing', entry.source);
    entry.vulcan.process(entry.source, (err, inlinedHtml) => {
      if (err !== null) {
        reject(`${entry.source}: ${err}`);
        return;
      }

      console.log('Writing', entry.output);
      fs.writeFileSync(entry.output, minifyHTML(inlinedHtml));
      resolve();
    });
  });
}

// Fetch all dependencies of main app and exclude them from panels
hyd.Analyzer.analyze('src/home-assistant.html')
    .then(function (analyzer) {
      return analyzer._getDependencies('src/home-assistant.html');
    })
    .then((deps) => {
      panelVulcan.stripExcludes = panelVulcan.stripExcludes.concat(deps);
    })
    // Chain all vulcanizing work as promises
    .then(() => toProcess.reduce(
      (p, entry) => p.then(() => vulcanizeEntry(entry)),
      Promise.resolve()));
