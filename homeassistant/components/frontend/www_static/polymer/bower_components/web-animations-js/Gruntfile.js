module.exports = function(grunt) {
  grunt.loadNpmTasks('grunt-contrib-uglify');
  grunt.loadNpmTasks('grunt-gjslint');
  grunt.loadNpmTasks('grunt-checkrepo');
  grunt.loadNpmTasks('grunt-karma');
  grunt.loadNpmTasks('grunt-saucelabs');
  grunt.loadNpmTasks('grunt-git-status');
  grunt.loadNpmTasks('grunt-template');

  var targetConfig = require('./target-config.js');

  var sourceMap = require('source-map');

  var config = {
    uglify: {},
    template: {},
    wrap: {},
    sourceMapConcat: {},
  };

  function concat(sources, target, defines) {
    config.uglify[target] = {
      options: {
        sourceMap: true,
        sourceMapName: target + '.map',
        wrap: false,
        compress: {
          global_defs: defines,
          dead_code: false
        },
        mangle: false
      },
      nonull: true,
      dest: target,
      src: sources
    };
    return 'uglify:' + target;
  }

  function compress(source, target, defines) {
    var name = concat([source], target, defines);
    var record = config.uglify[target];
    record.options.sourceMapIn = source + '.map';
    record.options.banner = grunt.file.read('templates/boilerplate');
    record.options.wrap = true;
    record.options.compress.dead_code = true;
    record.options.mangle = { eval: true };
    return name;
  }

  function genTarget(target) {
    var config = targetConfig[target];
    var newGens = [
      generateFromTemplate('templates/web-animations.js', {target: target}, target + '.dev.js'),
      generateFromTemplate('templates/web-animations.html', {src: config.src}, target + '.dev.html'),
      generateFromTemplate('templates/runner.html', {target: target}, 'test/runner-' + target + '.html')];
    return newGens;
  }

  function generateFromTemplate(source, data, target) {
    var targetSpec = {};
    targetSpec[target] = [source];
    config.template[target] = {
      options: {
        data: data
      },
      files: targetSpec
    }
    return 'template:' + target;
  }

  function guard(source, target) {
    config.wrap[target] = {
      source: source,
      preamble: '(function() {\n' +
                '  if (document.documentElement.animate) {\n' +
                '    var player = document.documentElement.animate([], 0);\n' +
                '    var load = true;\n' +
                '    if (player) {\n' +
                '      load = false;\n' +
                '      "play|currentTime|pause|reverse|playbackRate|cancel|finish|startTime|playState".split("|").forEach(function(t) {\n' +
                '        if (player[t] === undefined) {\n' +
                '          load = true;\n' +
                '        }\n' +
                '      });\n' +
                '    }\n' +
                '    if (!load) { return; }' +
                '  }\n',
      postamble: '})();'
    };
    return 'wrap:' + target;
  }

  function concatWithMaps(sources, target) {
    config.sourceMapConcat[target] = {
      sources: sources
    }
    return 'sourceMapConcat:' + target;
  };

  var concatDefines = {
    WEB_ANIMATIONS_TESTING: false
  };

  function buildWebAnimations1(target) {
    var config = targetConfig[target];
    return genTarget(target).concat([
      concat(config.scopeSrc.concat(config.sharedSrc).concat(config.webAnimations1Src), 'inter-raw-' + target + '.js', concatDefines),
      guard('inter-raw-' + target + '.js', 'inter-' + target + '.js'),
      compress('inter-' + target + '.js', target + '.min.js', concatDefines)
    ]);
  }

  function buildWebAnimationsNext(target) {
    var config = targetConfig[target];
    return genTarget(target).concat([
      concat(config.scopeSrc.concat(config.sharedSrc), 'inter-' + target + '-preamble.js', concatDefines),
      concat(config.webAnimations1Src, 'inter-component-' + target + 'web-animations-1.js', concatDefines),
      guard('inter-component-' + target + 'web-animations-1.js', 'inter-guarded-' + target + '-web-animations-1.js'),
      concat(config.webAnimationsNextSrc, 'inter-component-' + target + '.js', concatDefines),
      concatWithMaps(['inter-' + target + '-preamble.js', 'inter-guarded-' + target + '-web-animations-1.js', 'inter-component-' + target + '.js'],
          'inter-' + target + '.js'),
      compress('inter-' + target + '.js', target + '.min.js', concatDefines)
    ]);
  }

  grunt.registerTask('web-animations', buildWebAnimations1('web-animations'));
  grunt.registerTask('web-animations-next', buildWebAnimationsNext('web-animations-next'));
  grunt.registerTask('web-animations-next-lite', buildWebAnimationsNext('web-animations-next-lite'));

  var testTargets = {'web-animations': {}, 'web-animations-next': {}};

  grunt.initConfig({
    uglify: config.uglify,
    template: config.template,
    wrap: config.wrap,
    sourceMapConcat: config.sourceMapConcat,
    checkrepo: {
      all: {
        clean: true,
      },
    },
    'git-status': {
      all: {
      },
    },
    gjslint: {
      options: {
        flags: [
          '--nojsdoc',
          '--strict',
          '--disable 7,121,110', //   7: Wrong blank line count
                                 // 121: Illegal comma at end of object literal
                                 // 110: Line too long
        ],
        reporter: {
          name: 'console'
        }
      },
      all: {
        src: [
          'src/*.js',
          'test/*.js',
          'test/js/*.js',
        ],
      }
    },
    test: testTargets,
    sauce: testTargets,
  });


  grunt.task.registerMultiTask('test', 'Run <target> tests under Karma', function() {
    var done = this.async();
    var karmaConfig = require('karma/lib/config').parseConfig(require('path').resolve('test/karma-config.js'), {});
    var config = targetConfig[this.target];
    karmaConfig.files = ['test/runner.js'].concat(config.src, config.test);
    var karmaServer = require('karma').server;
    karmaServer.start(karmaConfig, function(exitCode) {
      done(exitCode === 0);
    });
  });

  grunt.task.registerMultiTask('sauce', 'Run <target> tests under Karma on Saucelabs', function() {
    var done = this.async();
    var karmaConfig = require('karma/lib/config').parseConfig(require('path').resolve('test/karma-config-ci.js'), {});
    var config = targetConfig[this.target];
    karmaConfig.files = ['test/runner.js'].concat(config.src, config.test);
    karmaConfig.sauceLabs.testName = 'web-animation-next ' + this.target + ' Unit tests';
    var karmaServer = require('karma').server;
    karmaServer.start(karmaConfig, function(exitCode) {
      done(exitCode === 0);
    });
  });

  grunt.task.registerMultiTask('sourceMapConcat', 'concat source files and produce combined source map',
    function() {
      var sources = this.data.sources.map(grunt.file.read);
      var sourceMaps = this.data.sources.map(function(f) { return grunt.file.read(f + '.map'); });
      var out = "";
      var outMapGenerator = new sourceMap.SourceMapGenerator({file: this.target});
      var lineDelta = 0;
      for (var i = 0; i < sources.length; i++) {
        out += sources[i];
        new sourceMap.SourceMapConsumer(sourceMaps[i]).eachMapping(function(mapping) {
          outMapGenerator.addMapping({
            generated: {line: mapping.generatedLine + lineDelta, column: mapping.generatedColumn},
            original: {line: mapping.originalLine, column: mapping.originalColumn},
            source: mapping.source, name: mapping.name});
        });
        var sourceLines = sources[i].split('\n');
        lineDelta += sourceLines.length;
        if (sources[i][sources[i].length - 1] !== '\n') {
          out += '\n';
        }
      }
      grunt.file.write(this.target, out);
      grunt.file.write(this.target + '.map', outMapGenerator.toString());
    });

  grunt.task.registerMultiTask('wrap', 'Wrap <target> source file and update source map',
    function() {
      var inFile = grunt.file.read(this.data.source);
      var inMap = grunt.file.read(this.data.source + '.map');
      var inLines = inFile.split('\n');
      var i = 0;

      // Discover copyright header
      while (inLines[i].length < 2 || inLines[i].substring(0, 2) == '//') {
        i++;
      }

      // Fix mapping footer
      var postamble = this.data.postamble;
      if (inLines[inLines.length - 1].substring(0, 21) == '//# sourceMappingURL=') {
        postamble += '\n//# sourceMappingURL=' + this.target + '.map';
      }

      if (i > 0) {
        var banner = inLines.slice(0, i).join('\n') + '\n';
      } else {
        var banner = '';
      }

      var source = inLines.slice(i, inLines.length - 1).join('\n');

      grunt.file.write(this.target, banner + this.data.preamble + source + postamble);
      var preLines = this.data.preamble.split('\n');
      var lineDelta = preLines.length;
      if (this.data.preamble[this.data.preamble.length - 1] == '\n') {
        var charDelta = 0;
      } else {
        var charDelta = preLines[lineDelta - 1].length;
        lineDelta -= 1;
      }
      var inMapConsumer = new sourceMap.SourceMapConsumer(inMap);
      var outMapGenerator = new sourceMap.SourceMapGenerator({file: this.target});
      inMapConsumer.eachMapping(function(mapping) {
        if (mapping.generatedLine == i + 1) {
          mapping.generatedColumn += charDelta;
        }
        mapping.generatedLine += lineDelta;
        outMapGenerator.addMapping(
          {generated: {line: mapping.generatedLine, column: mapping.generatedColumn},
          original: {line: mapping.originalLine, column: mapping.originalColumn},
          source: mapping.source, name: mapping.name});
      });
      grunt.file.write(this.target + '.map', outMapGenerator.toString());
    });

  grunt.task.registerTask('clean', 'Remove files generated by grunt', function() {
    grunt.file.expand('web-animations*').concat(grunt.file.expand('test/runner-*.html')).concat(grunt.file.expand('inter-*')).forEach(function(file) {
      grunt.file.delete(file);
      grunt.log.writeln('File ' + file + ' removed');
    });
  });

  grunt.task.registerTask('default', ['web-animations', 'web-animations-next', 'web-animations-next-lite', 'gjslint']);
};
