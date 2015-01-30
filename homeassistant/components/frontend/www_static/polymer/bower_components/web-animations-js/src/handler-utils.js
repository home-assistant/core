// Copyright 2014 Google Inc. All rights reserved.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
//   You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//   See the License for the specific language governing permissions and
// limitations under the License.

(function(scope) {

  // consume* functions return a 2 value array of [parsed-data, '' or not-yet consumed input]

  // Regex should be anchored with /^
  function consumeToken(regex, string) {
    var result = regex.exec(string);
    if (result) {
      result = regex.ignoreCase ? result[0].toLowerCase() : result[0];
      return [result, string.substr(result.length)];
    }
  }

  function consumeTrimmed(consumer, string) {
    string = string.replace(/^\s*/, '');
    var result = consumer(string);
    if (result) {
      return [result[0], result[1].replace(/^\s*/, '')];
    }
  }

  function consumeRepeated(consumer, separator, string) {
    consumer = consumeTrimmed.bind(null, consumer);
    var list = [];
    while (true) {
      var result = consumer(string);
      if (!result) {
        return [list, string];
      }
      list.push(result[0]);
      string = result[1];
      result = consumeToken(separator, string);
      if (!result || result[1] == '') {
        return [list, string];
      }
      string = result[1];
    }
  }

  // Consumes a token or expression with balanced parentheses
  function consumeParenthesised(parser, string) {
    var nesting = 0;
    for (var n = 0; n < string.length; n++) {
      if (/\s|,/.test(string[n]) && nesting == 0) {
        break;
      } else if (string[n] == '(') {
        nesting++;
      } else if (string[n] == ')') {
        nesting--;
        if (nesting == 0)
          n++;
        if (nesting <= 0)
          break;
      }
    }
    var parsed = parser(string.substr(0, n));
    return parsed == undefined ? undefined : [parsed, string.substr(n)];
  }

  function lcm(a, b) {
    var c = a;
    var d = b;
    while (c && d)
      c > d ? c %= d : d %= c;
    c = (a * b) / (c + d);
    return c;
  }

  function ignore(value) {
    return function(input) {
      var result = value(input);
      if (result)
        result[0] = undefined;
      return result;
    }
  }

  function optional(value, defaultValue) {
    return function(input) {
      var result = value(input);
      if (result)
        return result;
      return [defaultValue, input];
    }
  }

  function consumeList(list, input) {
    var output = [];
    for (var i = 0; i < list.length; i++) {
      var result = scope.consumeTrimmed(list[i], input);
      if (!result || result[0] == '')
        return;
      if (result[0] !== undefined)
        output.push(result[0]);
      input = result[1];
    }
    if (input == '') {
      return output;
    }
  }

  function mergeWrappedNestedRepeated(wrap, nestedMerge, separator, left, right) {
    var matchingLeft = [];
    var matchingRight = [];
    var reconsititution = [];
    var length = lcm(left.length, right.length);
    for (var i = 0; i < length; i++) {
      var thing = nestedMerge(left[i % left.length], right[i % right.length]);
      if (!thing) {
        return;
      }
      matchingLeft.push(thing[0]);
      matchingRight.push(thing[1]);
      reconsititution.push(thing[2]);
    }
    return [matchingLeft, matchingRight, function(positions) {
      var result = positions.map(function(position, i) {
        return reconsititution[i](position);
      }).join(separator);
      return wrap ? wrap(result) : result;
    }];
  }

  function mergeList(left, right, list) {
    var lefts = [];
    var rights = [];
    var functions = [];
    var j = 0;
    for (var i = 0; i < list.length; i++) {
      if (typeof list[i] == 'function') {
        var result = list[i](left[j], right[j++]);
        lefts.push(result[0]);
        rights.push(result[1]);
        functions.push(result[2]);
      } else {
        (function(pos) {
          lefts.push(false);
          rights.push(false);
          functions.push(function() { return list[pos]; });
        })(i);
      }
    }
    return [lefts, rights, function(results) {
      var result = '';
      for (var i = 0; i < results.length; i++) {
        result += functions[i](results[i]);
      }
      return result;
    }];
  }

  scope.consumeToken = consumeToken;
  scope.consumeTrimmed = consumeTrimmed;
  scope.consumeRepeated = consumeRepeated;
  scope.consumeParenthesised = consumeParenthesised;
  scope.ignore = ignore;
  scope.optional = optional;
  scope.consumeList = consumeList;
  scope.mergeNestedRepeated = mergeWrappedNestedRepeated.bind(null, null);
  scope.mergeWrappedNestedRepeated = mergeWrappedNestedRepeated;
  scope.mergeList = mergeList;

})(webAnimations1);
