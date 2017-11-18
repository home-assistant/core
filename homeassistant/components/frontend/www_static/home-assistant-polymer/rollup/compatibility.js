import config from './base-config';

export default Object.assign({}, config, {
  entry: 'src/compatibility.js',
  targets: [
    { dest: 'build/compatibility.js', format: 'iife' },
  ],
});
