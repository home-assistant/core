import config from './base-config';

export default Object.assign({}, config, {
  entry: 'panels/automation/editor.js',
  targets: [
    { dest: 'build-temp/editor.js', format: 'iife' },
  ],
});
