var Benchmark = require('benchmark'),
    moment = require("./../moment.js"),
    base = moment('2013-05-25');

module.exports = {
  name: 'clone',
  onComplete: function(){console.log('done');},
  fn: function(){base.clone();},
  async: true
};
