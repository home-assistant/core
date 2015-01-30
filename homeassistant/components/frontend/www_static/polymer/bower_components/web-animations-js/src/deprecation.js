// Copyright 2014 Google Inc. All rights reserved.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
//     You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//     See the License for the specific language governing permissions and
// limitations under the License.

(function(shared) {

  var silenced = {};

  shared.isDeprecated = function(feature, date, advice, plural) {
    var auxVerb = plural ? 'are' : 'is';
    var today = new Date();
    var expiry = new Date(date);
    expiry.setMonth(expiry.getMonth() + 3); // 3 months grace period

    if (today < expiry) {
      if (!(feature in silenced)) {
        console.warn('Web Animations: ' + feature + ' ' + auxVerb + ' deprecated and will stop working on ' + expiry.toDateString() + '. ' + advice);
      }
      silenced[feature] = true;
      return false;
    } else {
      return true;
    }
  };

  shared.deprecated = function(feature, date, advice, plural) {
    if (shared.isDeprecated(feature, date, advice, plural)) {
      throw new Error(feature + ' ' + auxVerb + ' no longer supported. ' + advice);
    }
  };

})(webAnimationsShared);
