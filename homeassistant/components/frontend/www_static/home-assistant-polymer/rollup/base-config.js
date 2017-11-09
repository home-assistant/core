import commonjs from 'rollup-plugin-commonjs';
import nodeResolve from 'rollup-plugin-node-resolve';
import replace from 'rollup-plugin-replace';
import babel from 'rollup-plugin-babel';
import uglify from 'rollup-plugin-uglify';

const DEV = !!JSON.parse(process.env.BUILD_DEV || 'true');
const DEMO = !!JSON.parse(process.env.BUILD_DEMO || 'false');

const plugins = [
  babel({
  }),

  nodeResolve({
    jsnext: true,
    main: true,
  }),

  commonjs(),

  replace({
    values: {
      __DEV__: JSON.stringify(DEV),
      __DEMO__: JSON.stringify(DEMO),
    },
  }),
];

if (!DEV) {
  plugins.push(uglify());
}

export default {
  format: 'iife',
  exports: 'none',
  treeshake: true,
  plugins,
};
