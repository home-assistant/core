/**
 * @license
 * Copyright (c) 2014 The Polymer Project Authors. All rights reserved.
 * This code may only be used under the BSD style license found at http://polymer.github.io/LICENSE.txt
 * The complete set of authors may be found at http://polymer.github.io/AUTHORS.txt
 * The complete set of contributors may be found at http://polymer.github.io/CONTRIBUTORS.txt
 * Code distributed by Google as part of the polymer project is also
 * subject to an additional IP rights grant found at http://polymer.github.io/PATENTS.txt
 */
// @version 0.5.4
if (typeof WeakMap === "undefined") {
  (function() {
    var defineProperty = Object.defineProperty;
    var counter = Date.now() % 1e9;
    var WeakMap = function() {
      this.name = "__st" + (Math.random() * 1e9 >>> 0) + (counter++ + "__");
    };
    WeakMap.prototype = {
      set: function(key, value) {
        var entry = key[this.name];
        if (entry && entry[0] === key) entry[1] = value; else defineProperty(key, this.name, {
          value: [ key, value ],
          writable: true
        });
        return this;
      },
      get: function(key) {
        var entry;
        return (entry = key[this.name]) && entry[0] === key ? entry[1] : undefined;
      },
      "delete": function(key) {
        var entry = key[this.name];
        if (!entry || entry[0] !== key) return false;
        entry[0] = entry[1] = undefined;
        return true;
      },
      has: function(key) {
        var entry = key[this.name];
        if (!entry) return false;
        return entry[0] === key;
      }
    };
    window.WeakMap = WeakMap;
  })();
}

window.ShadowDOMPolyfill = {};

(function(scope) {
  "use strict";
  var constructorTable = new WeakMap();
  var nativePrototypeTable = new WeakMap();
  var wrappers = Object.create(null);
  function detectEval() {
    if (typeof chrome !== "undefined" && chrome.app && chrome.app.runtime) {
      return false;
    }
    if (navigator.getDeviceStorage) {
      return false;
    }
    try {
      var f = new Function("return true;");
      return f();
    } catch (ex) {
      return false;
    }
  }
  var hasEval = detectEval();
  function assert(b) {
    if (!b) throw new Error("Assertion failed");
  }
  var defineProperty = Object.defineProperty;
  var getOwnPropertyNames = Object.getOwnPropertyNames;
  var getOwnPropertyDescriptor = Object.getOwnPropertyDescriptor;
  function mixin(to, from) {
    var names = getOwnPropertyNames(from);
    for (var i = 0; i < names.length; i++) {
      var name = names[i];
      defineProperty(to, name, getOwnPropertyDescriptor(from, name));
    }
    return to;
  }
  function mixinStatics(to, from) {
    var names = getOwnPropertyNames(from);
    for (var i = 0; i < names.length; i++) {
      var name = names[i];
      switch (name) {
       case "arguments":
       case "caller":
       case "length":
       case "name":
       case "prototype":
       case "toString":
        continue;
      }
      defineProperty(to, name, getOwnPropertyDescriptor(from, name));
    }
    return to;
  }
  function oneOf(object, propertyNames) {
    for (var i = 0; i < propertyNames.length; i++) {
      if (propertyNames[i] in object) return propertyNames[i];
    }
  }
  var nonEnumerableDataDescriptor = {
    value: undefined,
    configurable: true,
    enumerable: false,
    writable: true
  };
  function defineNonEnumerableDataProperty(object, name, value) {
    nonEnumerableDataDescriptor.value = value;
    defineProperty(object, name, nonEnumerableDataDescriptor);
  }
  getOwnPropertyNames(window);
  function getWrapperConstructor(node) {
    var nativePrototype = node.__proto__ || Object.getPrototypeOf(node);
    var wrapperConstructor = constructorTable.get(nativePrototype);
    if (wrapperConstructor) return wrapperConstructor;
    var parentWrapperConstructor = getWrapperConstructor(nativePrototype);
    var GeneratedWrapper = createWrapperConstructor(parentWrapperConstructor);
    registerInternal(nativePrototype, GeneratedWrapper, node);
    return GeneratedWrapper;
  }
  function addForwardingProperties(nativePrototype, wrapperPrototype) {
    installProperty(nativePrototype, wrapperPrototype, true);
  }
  function registerInstanceProperties(wrapperPrototype, instanceObject) {
    installProperty(instanceObject, wrapperPrototype, false);
  }
  var isFirefox = /Firefox/.test(navigator.userAgent);
  var dummyDescriptor = {
    get: function() {},
    set: function(v) {},
    configurable: true,
    enumerable: true
  };
  function isEventHandlerName(name) {
    return /^on[a-z]+$/.test(name);
  }
  function isIdentifierName(name) {
    return /^\w[a-zA-Z_0-9]*$/.test(name);
  }
  function getGetter(name) {
    return hasEval && isIdentifierName(name) ? new Function("return this.__impl4cf1e782hg__." + name) : function() {
      return this.__impl4cf1e782hg__[name];
    };
  }
  function getSetter(name) {
    return hasEval && isIdentifierName(name) ? new Function("v", "this.__impl4cf1e782hg__." + name + " = v") : function(v) {
      this.__impl4cf1e782hg__[name] = v;
    };
  }
  function getMethod(name) {
    return hasEval && isIdentifierName(name) ? new Function("return this.__impl4cf1e782hg__." + name + ".apply(this.__impl4cf1e782hg__, arguments)") : function() {
      return this.__impl4cf1e782hg__[name].apply(this.__impl4cf1e782hg__, arguments);
    };
  }
  function getDescriptor(source, name) {
    try {
      return Object.getOwnPropertyDescriptor(source, name);
    } catch (ex) {
      return dummyDescriptor;
    }
  }
  var isBrokenSafari = function() {
    var descr = Object.getOwnPropertyDescriptor(Node.prototype, "nodeType");
    return descr && !descr.get && !descr.set;
  }();
  function installProperty(source, target, allowMethod, opt_blacklist) {
    var names = getOwnPropertyNames(source);
    for (var i = 0; i < names.length; i++) {
      var name = names[i];
      if (name === "polymerBlackList_") continue;
      if (name in target) continue;
      if (source.polymerBlackList_ && source.polymerBlackList_[name]) continue;
      if (isFirefox) {
        source.__lookupGetter__(name);
      }
      var descriptor = getDescriptor(source, name);
      var getter, setter;
      if (allowMethod && typeof descriptor.value === "function") {
        target[name] = getMethod(name);
        continue;
      }
      var isEvent = isEventHandlerName(name);
      if (isEvent) getter = scope.getEventHandlerGetter(name); else getter = getGetter(name);
      if (descriptor.writable || descriptor.set || isBrokenSafari) {
        if (isEvent) setter = scope.getEventHandlerSetter(name); else setter = getSetter(name);
      }
      defineProperty(target, name, {
        get: getter,
        set: setter,
        configurable: descriptor.configurable,
        enumerable: descriptor.enumerable
      });
    }
  }
  function register(nativeConstructor, wrapperConstructor, opt_instance) {
    var nativePrototype = nativeConstructor.prototype;
    registerInternal(nativePrototype, wrapperConstructor, opt_instance);
    mixinStatics(wrapperConstructor, nativeConstructor);
  }
  function registerInternal(nativePrototype, wrapperConstructor, opt_instance) {
    var wrapperPrototype = wrapperConstructor.prototype;
    assert(constructorTable.get(nativePrototype) === undefined);
    constructorTable.set(nativePrototype, wrapperConstructor);
    nativePrototypeTable.set(wrapperPrototype, nativePrototype);
    addForwardingProperties(nativePrototype, wrapperPrototype);
    if (opt_instance) registerInstanceProperties(wrapperPrototype, opt_instance);
    defineNonEnumerableDataProperty(wrapperPrototype, "constructor", wrapperConstructor);
    wrapperConstructor.prototype = wrapperPrototype;
  }
  function isWrapperFor(wrapperConstructor, nativeConstructor) {
    return constructorTable.get(nativeConstructor.prototype) === wrapperConstructor;
  }
  function registerObject(object) {
    var nativePrototype = Object.getPrototypeOf(object);
    var superWrapperConstructor = getWrapperConstructor(nativePrototype);
    var GeneratedWrapper = createWrapperConstructor(superWrapperConstructor);
    registerInternal(nativePrototype, GeneratedWrapper, object);
    return GeneratedWrapper;
  }
  function createWrapperConstructor(superWrapperConstructor) {
    function GeneratedWrapper(node) {
      superWrapperConstructor.call(this, node);
    }
    var p = Object.create(superWrapperConstructor.prototype);
    p.constructor = GeneratedWrapper;
    GeneratedWrapper.prototype = p;
    return GeneratedWrapper;
  }
  function isWrapper(object) {
    return object && object.__impl4cf1e782hg__;
  }
  function isNative(object) {
    return !isWrapper(object);
  }
  function wrap(impl) {
    if (impl === null) return null;
    assert(isNative(impl));
    return impl.__wrapper8e3dd93a60__ || (impl.__wrapper8e3dd93a60__ = new (getWrapperConstructor(impl))(impl));
  }
  function unwrap(wrapper) {
    if (wrapper === null) return null;
    assert(isWrapper(wrapper));
    return wrapper.__impl4cf1e782hg__;
  }
  function unsafeUnwrap(wrapper) {
    return wrapper.__impl4cf1e782hg__;
  }
  function setWrapper(impl, wrapper) {
    wrapper.__impl4cf1e782hg__ = impl;
    impl.__wrapper8e3dd93a60__ = wrapper;
  }
  function unwrapIfNeeded(object) {
    return object && isWrapper(object) ? unwrap(object) : object;
  }
  function wrapIfNeeded(object) {
    return object && !isWrapper(object) ? wrap(object) : object;
  }
  function rewrap(node, wrapper) {
    if (wrapper === null) return;
    assert(isNative(node));
    assert(wrapper === undefined || isWrapper(wrapper));
    node.__wrapper8e3dd93a60__ = wrapper;
  }
  var getterDescriptor = {
    get: undefined,
    configurable: true,
    enumerable: true
  };
  function defineGetter(constructor, name, getter) {
    getterDescriptor.get = getter;
    defineProperty(constructor.prototype, name, getterDescriptor);
  }
  function defineWrapGetter(constructor, name) {
    defineGetter(constructor, name, function() {
      return wrap(this.__impl4cf1e782hg__[name]);
    });
  }
  function forwardMethodsToWrapper(constructors, names) {
    constructors.forEach(function(constructor) {
      names.forEach(function(name) {
        constructor.prototype[name] = function() {
          var w = wrapIfNeeded(this);
          return w[name].apply(w, arguments);
        };
      });
    });
  }
  scope.assert = assert;
  scope.constructorTable = constructorTable;
  scope.defineGetter = defineGetter;
  scope.defineWrapGetter = defineWrapGetter;
  scope.forwardMethodsToWrapper = forwardMethodsToWrapper;
  scope.isWrapper = isWrapper;
  scope.isWrapperFor = isWrapperFor;
  scope.mixin = mixin;
  scope.nativePrototypeTable = nativePrototypeTable;
  scope.oneOf = oneOf;
  scope.registerObject = registerObject;
  scope.registerWrapper = register;
  scope.rewrap = rewrap;
  scope.setWrapper = setWrapper;
  scope.unsafeUnwrap = unsafeUnwrap;
  scope.unwrap = unwrap;
  scope.unwrapIfNeeded = unwrapIfNeeded;
  scope.wrap = wrap;
  scope.wrapIfNeeded = wrapIfNeeded;
  scope.wrappers = wrappers;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  function newSplice(index, removed, addedCount) {
    return {
      index: index,
      removed: removed,
      addedCount: addedCount
    };
  }
  var EDIT_LEAVE = 0;
  var EDIT_UPDATE = 1;
  var EDIT_ADD = 2;
  var EDIT_DELETE = 3;
  function ArraySplice() {}
  ArraySplice.prototype = {
    calcEditDistances: function(current, currentStart, currentEnd, old, oldStart, oldEnd) {
      var rowCount = oldEnd - oldStart + 1;
      var columnCount = currentEnd - currentStart + 1;
      var distances = new Array(rowCount);
      for (var i = 0; i < rowCount; i++) {
        distances[i] = new Array(columnCount);
        distances[i][0] = i;
      }
      for (var j = 0; j < columnCount; j++) distances[0][j] = j;
      for (var i = 1; i < rowCount; i++) {
        for (var j = 1; j < columnCount; j++) {
          if (this.equals(current[currentStart + j - 1], old[oldStart + i - 1])) distances[i][j] = distances[i - 1][j - 1]; else {
            var north = distances[i - 1][j] + 1;
            var west = distances[i][j - 1] + 1;
            distances[i][j] = north < west ? north : west;
          }
        }
      }
      return distances;
    },
    spliceOperationsFromEditDistances: function(distances) {
      var i = distances.length - 1;
      var j = distances[0].length - 1;
      var current = distances[i][j];
      var edits = [];
      while (i > 0 || j > 0) {
        if (i == 0) {
          edits.push(EDIT_ADD);
          j--;
          continue;
        }
        if (j == 0) {
          edits.push(EDIT_DELETE);
          i--;
          continue;
        }
        var northWest = distances[i - 1][j - 1];
        var west = distances[i - 1][j];
        var north = distances[i][j - 1];
        var min;
        if (west < north) min = west < northWest ? west : northWest; else min = north < northWest ? north : northWest;
        if (min == northWest) {
          if (northWest == current) {
            edits.push(EDIT_LEAVE);
          } else {
            edits.push(EDIT_UPDATE);
            current = northWest;
          }
          i--;
          j--;
        } else if (min == west) {
          edits.push(EDIT_DELETE);
          i--;
          current = west;
        } else {
          edits.push(EDIT_ADD);
          j--;
          current = north;
        }
      }
      edits.reverse();
      return edits;
    },
    calcSplices: function(current, currentStart, currentEnd, old, oldStart, oldEnd) {
      var prefixCount = 0;
      var suffixCount = 0;
      var minLength = Math.min(currentEnd - currentStart, oldEnd - oldStart);
      if (currentStart == 0 && oldStart == 0) prefixCount = this.sharedPrefix(current, old, minLength);
      if (currentEnd == current.length && oldEnd == old.length) suffixCount = this.sharedSuffix(current, old, minLength - prefixCount);
      currentStart += prefixCount;
      oldStart += prefixCount;
      currentEnd -= suffixCount;
      oldEnd -= suffixCount;
      if (currentEnd - currentStart == 0 && oldEnd - oldStart == 0) return [];
      if (currentStart == currentEnd) {
        var splice = newSplice(currentStart, [], 0);
        while (oldStart < oldEnd) splice.removed.push(old[oldStart++]);
        return [ splice ];
      } else if (oldStart == oldEnd) return [ newSplice(currentStart, [], currentEnd - currentStart) ];
      var ops = this.spliceOperationsFromEditDistances(this.calcEditDistances(current, currentStart, currentEnd, old, oldStart, oldEnd));
      var splice = undefined;
      var splices = [];
      var index = currentStart;
      var oldIndex = oldStart;
      for (var i = 0; i < ops.length; i++) {
        switch (ops[i]) {
         case EDIT_LEAVE:
          if (splice) {
            splices.push(splice);
            splice = undefined;
          }
          index++;
          oldIndex++;
          break;

         case EDIT_UPDATE:
          if (!splice) splice = newSplice(index, [], 0);
          splice.addedCount++;
          index++;
          splice.removed.push(old[oldIndex]);
          oldIndex++;
          break;

         case EDIT_ADD:
          if (!splice) splice = newSplice(index, [], 0);
          splice.addedCount++;
          index++;
          break;

         case EDIT_DELETE:
          if (!splice) splice = newSplice(index, [], 0);
          splice.removed.push(old[oldIndex]);
          oldIndex++;
          break;
        }
      }
      if (splice) {
        splices.push(splice);
      }
      return splices;
    },
    sharedPrefix: function(current, old, searchLength) {
      for (var i = 0; i < searchLength; i++) if (!this.equals(current[i], old[i])) return i;
      return searchLength;
    },
    sharedSuffix: function(current, old, searchLength) {
      var index1 = current.length;
      var index2 = old.length;
      var count = 0;
      while (count < searchLength && this.equals(current[--index1], old[--index2])) count++;
      return count;
    },
    calculateSplices: function(current, previous) {
      return this.calcSplices(current, 0, current.length, previous, 0, previous.length);
    },
    equals: function(currentValue, previousValue) {
      return currentValue === previousValue;
    }
  };
  scope.ArraySplice = ArraySplice;
})(window.ShadowDOMPolyfill);

(function(context) {
  "use strict";
  var OriginalMutationObserver = window.MutationObserver;
  var callbacks = [];
  var pending = false;
  var timerFunc;
  function handle() {
    pending = false;
    var copies = callbacks.slice(0);
    callbacks = [];
    for (var i = 0; i < copies.length; i++) {
      (0, copies[i])();
    }
  }
  if (OriginalMutationObserver) {
    var counter = 1;
    var observer = new OriginalMutationObserver(handle);
    var textNode = document.createTextNode(counter);
    observer.observe(textNode, {
      characterData: true
    });
    timerFunc = function() {
      counter = (counter + 1) % 2;
      textNode.data = counter;
    };
  } else {
    timerFunc = window.setTimeout;
  }
  function setEndOfMicrotask(func) {
    callbacks.push(func);
    if (pending) return;
    pending = true;
    timerFunc(handle, 0);
  }
  context.setEndOfMicrotask = setEndOfMicrotask;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var setEndOfMicrotask = scope.setEndOfMicrotask;
  var wrapIfNeeded = scope.wrapIfNeeded;
  var wrappers = scope.wrappers;
  var registrationsTable = new WeakMap();
  var globalMutationObservers = [];
  var isScheduled = false;
  function scheduleCallback(observer) {
    if (observer.scheduled_) return;
    observer.scheduled_ = true;
    globalMutationObservers.push(observer);
    if (isScheduled) return;
    setEndOfMicrotask(notifyObservers);
    isScheduled = true;
  }
  function notifyObservers() {
    isScheduled = false;
    while (globalMutationObservers.length) {
      var notifyList = globalMutationObservers;
      globalMutationObservers = [];
      notifyList.sort(function(x, y) {
        return x.uid_ - y.uid_;
      });
      for (var i = 0; i < notifyList.length; i++) {
        var mo = notifyList[i];
        mo.scheduled_ = false;
        var queue = mo.takeRecords();
        removeTransientObserversFor(mo);
        if (queue.length) {
          mo.callback_(queue, mo);
        }
      }
    }
  }
  function MutationRecord(type, target) {
    this.type = type;
    this.target = target;
    this.addedNodes = new wrappers.NodeList();
    this.removedNodes = new wrappers.NodeList();
    this.previousSibling = null;
    this.nextSibling = null;
    this.attributeName = null;
    this.attributeNamespace = null;
    this.oldValue = null;
  }
  function registerTransientObservers(ancestor, node) {
    for (;ancestor; ancestor = ancestor.parentNode) {
      var registrations = registrationsTable.get(ancestor);
      if (!registrations) continue;
      for (var i = 0; i < registrations.length; i++) {
        var registration = registrations[i];
        if (registration.options.subtree) registration.addTransientObserver(node);
      }
    }
  }
  function removeTransientObserversFor(observer) {
    for (var i = 0; i < observer.nodes_.length; i++) {
      var node = observer.nodes_[i];
      var registrations = registrationsTable.get(node);
      if (!registrations) return;
      for (var j = 0; j < registrations.length; j++) {
        var registration = registrations[j];
        if (registration.observer === observer) registration.removeTransientObservers();
      }
    }
  }
  function enqueueMutation(target, type, data) {
    var interestedObservers = Object.create(null);
    var associatedStrings = Object.create(null);
    for (var node = target; node; node = node.parentNode) {
      var registrations = registrationsTable.get(node);
      if (!registrations) continue;
      for (var j = 0; j < registrations.length; j++) {
        var registration = registrations[j];
        var options = registration.options;
        if (node !== target && !options.subtree) continue;
        if (type === "attributes" && !options.attributes) continue;
        if (type === "attributes" && options.attributeFilter && (data.namespace !== null || options.attributeFilter.indexOf(data.name) === -1)) {
          continue;
        }
        if (type === "characterData" && !options.characterData) continue;
        if (type === "childList" && !options.childList) continue;
        var observer = registration.observer;
        interestedObservers[observer.uid_] = observer;
        if (type === "attributes" && options.attributeOldValue || type === "characterData" && options.characterDataOldValue) {
          associatedStrings[observer.uid_] = data.oldValue;
        }
      }
    }
    for (var uid in interestedObservers) {
      var observer = interestedObservers[uid];
      var record = new MutationRecord(type, target);
      if ("name" in data && "namespace" in data) {
        record.attributeName = data.name;
        record.attributeNamespace = data.namespace;
      }
      if (data.addedNodes) record.addedNodes = data.addedNodes;
      if (data.removedNodes) record.removedNodes = data.removedNodes;
      if (data.previousSibling) record.previousSibling = data.previousSibling;
      if (data.nextSibling) record.nextSibling = data.nextSibling;
      if (associatedStrings[uid] !== undefined) record.oldValue = associatedStrings[uid];
      scheduleCallback(observer);
      observer.records_.push(record);
    }
  }
  var slice = Array.prototype.slice;
  function MutationObserverOptions(options) {
    this.childList = !!options.childList;
    this.subtree = !!options.subtree;
    if (!("attributes" in options) && ("attributeOldValue" in options || "attributeFilter" in options)) {
      this.attributes = true;
    } else {
      this.attributes = !!options.attributes;
    }
    if ("characterDataOldValue" in options && !("characterData" in options)) this.characterData = true; else this.characterData = !!options.characterData;
    if (!this.attributes && (options.attributeOldValue || "attributeFilter" in options) || !this.characterData && options.characterDataOldValue) {
      throw new TypeError();
    }
    this.characterData = !!options.characterData;
    this.attributeOldValue = !!options.attributeOldValue;
    this.characterDataOldValue = !!options.characterDataOldValue;
    if ("attributeFilter" in options) {
      if (options.attributeFilter == null || typeof options.attributeFilter !== "object") {
        throw new TypeError();
      }
      this.attributeFilter = slice.call(options.attributeFilter);
    } else {
      this.attributeFilter = null;
    }
  }
  var uidCounter = 0;
  function MutationObserver(callback) {
    this.callback_ = callback;
    this.nodes_ = [];
    this.records_ = [];
    this.uid_ = ++uidCounter;
    this.scheduled_ = false;
  }
  MutationObserver.prototype = {
    constructor: MutationObserver,
    observe: function(target, options) {
      target = wrapIfNeeded(target);
      var newOptions = new MutationObserverOptions(options);
      var registration;
      var registrations = registrationsTable.get(target);
      if (!registrations) registrationsTable.set(target, registrations = []);
      for (var i = 0; i < registrations.length; i++) {
        if (registrations[i].observer === this) {
          registration = registrations[i];
          registration.removeTransientObservers();
          registration.options = newOptions;
        }
      }
      if (!registration) {
        registration = new Registration(this, target, newOptions);
        registrations.push(registration);
        this.nodes_.push(target);
      }
    },
    disconnect: function() {
      this.nodes_.forEach(function(node) {
        var registrations = registrationsTable.get(node);
        for (var i = 0; i < registrations.length; i++) {
          var registration = registrations[i];
          if (registration.observer === this) {
            registrations.splice(i, 1);
            break;
          }
        }
      }, this);
      this.records_ = [];
    },
    takeRecords: function() {
      var copyOfRecords = this.records_;
      this.records_ = [];
      return copyOfRecords;
    }
  };
  function Registration(observer, target, options) {
    this.observer = observer;
    this.target = target;
    this.options = options;
    this.transientObservedNodes = [];
  }
  Registration.prototype = {
    addTransientObserver: function(node) {
      if (node === this.target) return;
      scheduleCallback(this.observer);
      this.transientObservedNodes.push(node);
      var registrations = registrationsTable.get(node);
      if (!registrations) registrationsTable.set(node, registrations = []);
      registrations.push(this);
    },
    removeTransientObservers: function() {
      var transientObservedNodes = this.transientObservedNodes;
      this.transientObservedNodes = [];
      for (var i = 0; i < transientObservedNodes.length; i++) {
        var node = transientObservedNodes[i];
        var registrations = registrationsTable.get(node);
        for (var j = 0; j < registrations.length; j++) {
          if (registrations[j] === this) {
            registrations.splice(j, 1);
            break;
          }
        }
      }
    }
  };
  scope.enqueueMutation = enqueueMutation;
  scope.registerTransientObservers = registerTransientObservers;
  scope.wrappers.MutationObserver = MutationObserver;
  scope.wrappers.MutationRecord = MutationRecord;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  function TreeScope(root, parent) {
    this.root = root;
    this.parent = parent;
  }
  TreeScope.prototype = {
    get renderer() {
      if (this.root instanceof scope.wrappers.ShadowRoot) {
        return scope.getRendererForHost(this.root.host);
      }
      return null;
    },
    contains: function(treeScope) {
      for (;treeScope; treeScope = treeScope.parent) {
        if (treeScope === this) return true;
      }
      return false;
    }
  };
  function setTreeScope(node, treeScope) {
    if (node.treeScope_ !== treeScope) {
      node.treeScope_ = treeScope;
      for (var sr = node.shadowRoot; sr; sr = sr.olderShadowRoot) {
        sr.treeScope_.parent = treeScope;
      }
      for (var child = node.firstChild; child; child = child.nextSibling) {
        setTreeScope(child, treeScope);
      }
    }
  }
  function getTreeScope(node) {
    if (node instanceof scope.wrappers.Window) {
      debugger;
    }
    if (node.treeScope_) return node.treeScope_;
    var parent = node.parentNode;
    var treeScope;
    if (parent) treeScope = getTreeScope(parent); else treeScope = new TreeScope(node, null);
    return node.treeScope_ = treeScope;
  }
  scope.TreeScope = TreeScope;
  scope.getTreeScope = getTreeScope;
  scope.setTreeScope = setTreeScope;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var forwardMethodsToWrapper = scope.forwardMethodsToWrapper;
  var getTreeScope = scope.getTreeScope;
  var mixin = scope.mixin;
  var registerWrapper = scope.registerWrapper;
  var setWrapper = scope.setWrapper;
  var unsafeUnwrap = scope.unsafeUnwrap;
  var unwrap = scope.unwrap;
  var wrap = scope.wrap;
  var wrappers = scope.wrappers;
  var wrappedFuns = new WeakMap();
  var listenersTable = new WeakMap();
  var handledEventsTable = new WeakMap();
  var currentlyDispatchingEvents = new WeakMap();
  var targetTable = new WeakMap();
  var currentTargetTable = new WeakMap();
  var relatedTargetTable = new WeakMap();
  var eventPhaseTable = new WeakMap();
  var stopPropagationTable = new WeakMap();
  var stopImmediatePropagationTable = new WeakMap();
  var eventHandlersTable = new WeakMap();
  var eventPathTable = new WeakMap();
  function isShadowRoot(node) {
    return node instanceof wrappers.ShadowRoot;
  }
  function rootOfNode(node) {
    return getTreeScope(node).root;
  }
  function getEventPath(node, event) {
    var path = [];
    var current = node;
    path.push(current);
    while (current) {
      var destinationInsertionPoints = getDestinationInsertionPoints(current);
      if (destinationInsertionPoints && destinationInsertionPoints.length > 0) {
        for (var i = 0; i < destinationInsertionPoints.length; i++) {
          var insertionPoint = destinationInsertionPoints[i];
          if (isShadowInsertionPoint(insertionPoint)) {
            var shadowRoot = rootOfNode(insertionPoint);
            var olderShadowRoot = shadowRoot.olderShadowRoot;
            if (olderShadowRoot) path.push(olderShadowRoot);
          }
          path.push(insertionPoint);
        }
        current = destinationInsertionPoints[destinationInsertionPoints.length - 1];
      } else {
        if (isShadowRoot(current)) {
          if (inSameTree(node, current) && eventMustBeStopped(event)) {
            break;
          }
          current = current.host;
          path.push(current);
        } else {
          current = current.parentNode;
          if (current) path.push(current);
        }
      }
    }
    return path;
  }
  function eventMustBeStopped(event) {
    if (!event) return false;
    switch (event.type) {
     case "abort":
     case "error":
     case "select":
     case "change":
     case "load":
     case "reset":
     case "resize":
     case "scroll":
     case "selectstart":
      return true;
    }
    return false;
  }
  function isShadowInsertionPoint(node) {
    return node instanceof HTMLShadowElement;
  }
  function getDestinationInsertionPoints(node) {
    return scope.getDestinationInsertionPoints(node);
  }
  function eventRetargetting(path, currentTarget) {
    if (path.length === 0) return currentTarget;
    if (currentTarget instanceof wrappers.Window) currentTarget = currentTarget.document;
    var currentTargetTree = getTreeScope(currentTarget);
    var originalTarget = path[0];
    var originalTargetTree = getTreeScope(originalTarget);
    var relativeTargetTree = lowestCommonInclusiveAncestor(currentTargetTree, originalTargetTree);
    for (var i = 0; i < path.length; i++) {
      var node = path[i];
      if (getTreeScope(node) === relativeTargetTree) return node;
    }
    return path[path.length - 1];
  }
  function getTreeScopeAncestors(treeScope) {
    var ancestors = [];
    for (;treeScope; treeScope = treeScope.parent) {
      ancestors.push(treeScope);
    }
    return ancestors;
  }
  function lowestCommonInclusiveAncestor(tsA, tsB) {
    var ancestorsA = getTreeScopeAncestors(tsA);
    var ancestorsB = getTreeScopeAncestors(tsB);
    var result = null;
    while (ancestorsA.length > 0 && ancestorsB.length > 0) {
      var a = ancestorsA.pop();
      var b = ancestorsB.pop();
      if (a === b) result = a; else break;
    }
    return result;
  }
  function getTreeScopeRoot(ts) {
    if (!ts.parent) return ts;
    return getTreeScopeRoot(ts.parent);
  }
  function relatedTargetResolution(event, currentTarget, relatedTarget) {
    if (currentTarget instanceof wrappers.Window) currentTarget = currentTarget.document;
    var currentTargetTree = getTreeScope(currentTarget);
    var relatedTargetTree = getTreeScope(relatedTarget);
    var relatedTargetEventPath = getEventPath(relatedTarget, event);
    var lowestCommonAncestorTree;
    var lowestCommonAncestorTree = lowestCommonInclusiveAncestor(currentTargetTree, relatedTargetTree);
    if (!lowestCommonAncestorTree) lowestCommonAncestorTree = relatedTargetTree.root;
    for (var commonAncestorTree = lowestCommonAncestorTree; commonAncestorTree; commonAncestorTree = commonAncestorTree.parent) {
      var adjustedRelatedTarget;
      for (var i = 0; i < relatedTargetEventPath.length; i++) {
        var node = relatedTargetEventPath[i];
        if (getTreeScope(node) === commonAncestorTree) return node;
      }
    }
    return null;
  }
  function inSameTree(a, b) {
    return getTreeScope(a) === getTreeScope(b);
  }
  var NONE = 0;
  var CAPTURING_PHASE = 1;
  var AT_TARGET = 2;
  var BUBBLING_PHASE = 3;
  var pendingError;
  function dispatchOriginalEvent(originalEvent) {
    if (handledEventsTable.get(originalEvent)) return;
    handledEventsTable.set(originalEvent, true);
    dispatchEvent(wrap(originalEvent), wrap(originalEvent.target));
    if (pendingError) {
      var err = pendingError;
      pendingError = null;
      throw err;
    }
  }
  function isLoadLikeEvent(event) {
    switch (event.type) {
     case "load":
     case "beforeunload":
     case "unload":
      return true;
    }
    return false;
  }
  function dispatchEvent(event, originalWrapperTarget) {
    if (currentlyDispatchingEvents.get(event)) throw new Error("InvalidStateError");
    currentlyDispatchingEvents.set(event, true);
    scope.renderAllPending();
    var eventPath;
    var overrideTarget;
    var win;
    if (isLoadLikeEvent(event) && !event.bubbles) {
      var doc = originalWrapperTarget;
      if (doc instanceof wrappers.Document && (win = doc.defaultView)) {
        overrideTarget = doc;
        eventPath = [];
      }
    }
    if (!eventPath) {
      if (originalWrapperTarget instanceof wrappers.Window) {
        win = originalWrapperTarget;
        eventPath = [];
      } else {
        eventPath = getEventPath(originalWrapperTarget, event);
        if (!isLoadLikeEvent(event)) {
          var doc = eventPath[eventPath.length - 1];
          if (doc instanceof wrappers.Document) win = doc.defaultView;
        }
      }
    }
    eventPathTable.set(event, eventPath);
    if (dispatchCapturing(event, eventPath, win, overrideTarget)) {
      if (dispatchAtTarget(event, eventPath, win, overrideTarget)) {
        dispatchBubbling(event, eventPath, win, overrideTarget);
      }
    }
    eventPhaseTable.set(event, NONE);
    currentTargetTable.delete(event, null);
    currentlyDispatchingEvents.delete(event);
    return event.defaultPrevented;
  }
  function dispatchCapturing(event, eventPath, win, overrideTarget) {
    var phase = CAPTURING_PHASE;
    if (win) {
      if (!invoke(win, event, phase, eventPath, overrideTarget)) return false;
    }
    for (var i = eventPath.length - 1; i > 0; i--) {
      if (!invoke(eventPath[i], event, phase, eventPath, overrideTarget)) return false;
    }
    return true;
  }
  function dispatchAtTarget(event, eventPath, win, overrideTarget) {
    var phase = AT_TARGET;
    var currentTarget = eventPath[0] || win;
    return invoke(currentTarget, event, phase, eventPath, overrideTarget);
  }
  function dispatchBubbling(event, eventPath, win, overrideTarget) {
    var phase = BUBBLING_PHASE;
    for (var i = 1; i < eventPath.length; i++) {
      if (!invoke(eventPath[i], event, phase, eventPath, overrideTarget)) return;
    }
    if (win && eventPath.length > 0) {
      invoke(win, event, phase, eventPath, overrideTarget);
    }
  }
  function invoke(currentTarget, event, phase, eventPath, overrideTarget) {
    var listeners = listenersTable.get(currentTarget);
    if (!listeners) return true;
    var target = overrideTarget || eventRetargetting(eventPath, currentTarget);
    if (target === currentTarget) {
      if (phase === CAPTURING_PHASE) return true;
      if (phase === BUBBLING_PHASE) phase = AT_TARGET;
    } else if (phase === BUBBLING_PHASE && !event.bubbles) {
      return true;
    }
    if ("relatedTarget" in event) {
      var originalEvent = unwrap(event);
      var unwrappedRelatedTarget = originalEvent.relatedTarget;
      if (unwrappedRelatedTarget) {
        if (unwrappedRelatedTarget instanceof Object && unwrappedRelatedTarget.addEventListener) {
          var relatedTarget = wrap(unwrappedRelatedTarget);
          var adjusted = relatedTargetResolution(event, currentTarget, relatedTarget);
          if (adjusted === target) return true;
        } else {
          adjusted = null;
        }
        relatedTargetTable.set(event, adjusted);
      }
    }
    eventPhaseTable.set(event, phase);
    var type = event.type;
    var anyRemoved = false;
    targetTable.set(event, target);
    currentTargetTable.set(event, currentTarget);
    listeners.depth++;
    for (var i = 0, len = listeners.length; i < len; i++) {
      var listener = listeners[i];
      if (listener.removed) {
        anyRemoved = true;
        continue;
      }
      if (listener.type !== type || !listener.capture && phase === CAPTURING_PHASE || listener.capture && phase === BUBBLING_PHASE) {
        continue;
      }
      try {
        if (typeof listener.handler === "function") listener.handler.call(currentTarget, event); else listener.handler.handleEvent(event);
        if (stopImmediatePropagationTable.get(event)) return false;
      } catch (ex) {
        if (!pendingError) pendingError = ex;
      }
    }
    listeners.depth--;
    if (anyRemoved && listeners.depth === 0) {
      var copy = listeners.slice();
      listeners.length = 0;
      for (var i = 0; i < copy.length; i++) {
        if (!copy[i].removed) listeners.push(copy[i]);
      }
    }
    return !stopPropagationTable.get(event);
  }
  function Listener(type, handler, capture) {
    this.type = type;
    this.handler = handler;
    this.capture = Boolean(capture);
  }
  Listener.prototype = {
    equals: function(that) {
      return this.handler === that.handler && this.type === that.type && this.capture === that.capture;
    },
    get removed() {
      return this.handler === null;
    },
    remove: function() {
      this.handler = null;
    }
  };
  var OriginalEvent = window.Event;
  OriginalEvent.prototype.polymerBlackList_ = {
    returnValue: true,
    keyLocation: true
  };
  function Event(type, options) {
    if (type instanceof OriginalEvent) {
      var impl = type;
      if (!OriginalBeforeUnloadEvent && impl.type === "beforeunload" && !(this instanceof BeforeUnloadEvent)) {
        return new BeforeUnloadEvent(impl);
      }
      setWrapper(impl, this);
    } else {
      return wrap(constructEvent(OriginalEvent, "Event", type, options));
    }
  }
  Event.prototype = {
    get target() {
      return targetTable.get(this);
    },
    get currentTarget() {
      return currentTargetTable.get(this);
    },
    get eventPhase() {
      return eventPhaseTable.get(this);
    },
    get path() {
      var eventPath = eventPathTable.get(this);
      if (!eventPath) return [];
      return eventPath.slice();
    },
    stopPropagation: function() {
      stopPropagationTable.set(this, true);
    },
    stopImmediatePropagation: function() {
      stopPropagationTable.set(this, true);
      stopImmediatePropagationTable.set(this, true);
    }
  };
  registerWrapper(OriginalEvent, Event, document.createEvent("Event"));
  function unwrapOptions(options) {
    if (!options || !options.relatedTarget) return options;
    return Object.create(options, {
      relatedTarget: {
        value: unwrap(options.relatedTarget)
      }
    });
  }
  function registerGenericEvent(name, SuperEvent, prototype) {
    var OriginalEvent = window[name];
    var GenericEvent = function(type, options) {
      if (type instanceof OriginalEvent) setWrapper(type, this); else return wrap(constructEvent(OriginalEvent, name, type, options));
    };
    GenericEvent.prototype = Object.create(SuperEvent.prototype);
    if (prototype) mixin(GenericEvent.prototype, prototype);
    if (OriginalEvent) {
      try {
        registerWrapper(OriginalEvent, GenericEvent, new OriginalEvent("temp"));
      } catch (ex) {
        registerWrapper(OriginalEvent, GenericEvent, document.createEvent(name));
      }
    }
    return GenericEvent;
  }
  var UIEvent = registerGenericEvent("UIEvent", Event);
  var CustomEvent = registerGenericEvent("CustomEvent", Event);
  var relatedTargetProto = {
    get relatedTarget() {
      var relatedTarget = relatedTargetTable.get(this);
      if (relatedTarget !== undefined) return relatedTarget;
      return wrap(unwrap(this).relatedTarget);
    }
  };
  function getInitFunction(name, relatedTargetIndex) {
    return function() {
      arguments[relatedTargetIndex] = unwrap(arguments[relatedTargetIndex]);
      var impl = unwrap(this);
      impl[name].apply(impl, arguments);
    };
  }
  var mouseEventProto = mixin({
    initMouseEvent: getInitFunction("initMouseEvent", 14)
  }, relatedTargetProto);
  var focusEventProto = mixin({
    initFocusEvent: getInitFunction("initFocusEvent", 5)
  }, relatedTargetProto);
  var MouseEvent = registerGenericEvent("MouseEvent", UIEvent, mouseEventProto);
  var FocusEvent = registerGenericEvent("FocusEvent", UIEvent, focusEventProto);
  var defaultInitDicts = Object.create(null);
  var supportsEventConstructors = function() {
    try {
      new window.FocusEvent("focus");
    } catch (ex) {
      return false;
    }
    return true;
  }();
  function constructEvent(OriginalEvent, name, type, options) {
    if (supportsEventConstructors) return new OriginalEvent(type, unwrapOptions(options));
    var event = unwrap(document.createEvent(name));
    var defaultDict = defaultInitDicts[name];
    var args = [ type ];
    Object.keys(defaultDict).forEach(function(key) {
      var v = options != null && key in options ? options[key] : defaultDict[key];
      if (key === "relatedTarget") v = unwrap(v);
      args.push(v);
    });
    event["init" + name].apply(event, args);
    return event;
  }
  if (!supportsEventConstructors) {
    var configureEventConstructor = function(name, initDict, superName) {
      if (superName) {
        var superDict = defaultInitDicts[superName];
        initDict = mixin(mixin({}, superDict), initDict);
      }
      defaultInitDicts[name] = initDict;
    };
    configureEventConstructor("Event", {
      bubbles: false,
      cancelable: false
    });
    configureEventConstructor("CustomEvent", {
      detail: null
    }, "Event");
    configureEventConstructor("UIEvent", {
      view: null,
      detail: 0
    }, "Event");
    configureEventConstructor("MouseEvent", {
      screenX: 0,
      screenY: 0,
      clientX: 0,
      clientY: 0,
      ctrlKey: false,
      altKey: false,
      shiftKey: false,
      metaKey: false,
      button: 0,
      relatedTarget: null
    }, "UIEvent");
    configureEventConstructor("FocusEvent", {
      relatedTarget: null
    }, "UIEvent");
  }
  var OriginalBeforeUnloadEvent = window.BeforeUnloadEvent;
  function BeforeUnloadEvent(impl) {
    Event.call(this, impl);
  }
  BeforeUnloadEvent.prototype = Object.create(Event.prototype);
  mixin(BeforeUnloadEvent.prototype, {
    get returnValue() {
      return unsafeUnwrap(this).returnValue;
    },
    set returnValue(v) {
      unsafeUnwrap(this).returnValue = v;
    }
  });
  if (OriginalBeforeUnloadEvent) registerWrapper(OriginalBeforeUnloadEvent, BeforeUnloadEvent);
  function isValidListener(fun) {
    if (typeof fun === "function") return true;
    return fun && fun.handleEvent;
  }
  function isMutationEvent(type) {
    switch (type) {
     case "DOMAttrModified":
     case "DOMAttributeNameChanged":
     case "DOMCharacterDataModified":
     case "DOMElementNameChanged":
     case "DOMNodeInserted":
     case "DOMNodeInsertedIntoDocument":
     case "DOMNodeRemoved":
     case "DOMNodeRemovedFromDocument":
     case "DOMSubtreeModified":
      return true;
    }
    return false;
  }
  var OriginalEventTarget = window.EventTarget;
  function EventTarget(impl) {
    setWrapper(impl, this);
  }
  var methodNames = [ "addEventListener", "removeEventListener", "dispatchEvent" ];
  [ Node, Window ].forEach(function(constructor) {
    var p = constructor.prototype;
    methodNames.forEach(function(name) {
      Object.defineProperty(p, name + "_", {
        value: p[name]
      });
    });
  });
  function getTargetToListenAt(wrapper) {
    if (wrapper instanceof wrappers.ShadowRoot) wrapper = wrapper.host;
    return unwrap(wrapper);
  }
  EventTarget.prototype = {
    addEventListener: function(type, fun, capture) {
      if (!isValidListener(fun) || isMutationEvent(type)) return;
      var listener = new Listener(type, fun, capture);
      var listeners = listenersTable.get(this);
      if (!listeners) {
        listeners = [];
        listeners.depth = 0;
        listenersTable.set(this, listeners);
      } else {
        for (var i = 0; i < listeners.length; i++) {
          if (listener.equals(listeners[i])) return;
        }
      }
      listeners.push(listener);
      var target = getTargetToListenAt(this);
      target.addEventListener_(type, dispatchOriginalEvent, true);
    },
    removeEventListener: function(type, fun, capture) {
      capture = Boolean(capture);
      var listeners = listenersTable.get(this);
      if (!listeners) return;
      var count = 0, found = false;
      for (var i = 0; i < listeners.length; i++) {
        if (listeners[i].type === type && listeners[i].capture === capture) {
          count++;
          if (listeners[i].handler === fun) {
            found = true;
            listeners[i].remove();
          }
        }
      }
      if (found && count === 1) {
        var target = getTargetToListenAt(this);
        target.removeEventListener_(type, dispatchOriginalEvent, true);
      }
    },
    dispatchEvent: function(event) {
      var nativeEvent = unwrap(event);
      var eventType = nativeEvent.type;
      handledEventsTable.set(nativeEvent, false);
      scope.renderAllPending();
      var tempListener;
      if (!hasListenerInAncestors(this, eventType)) {
        tempListener = function() {};
        this.addEventListener(eventType, tempListener, true);
      }
      try {
        return unwrap(this).dispatchEvent_(nativeEvent);
      } finally {
        if (tempListener) this.removeEventListener(eventType, tempListener, true);
      }
    }
  };
  function hasListener(node, type) {
    var listeners = listenersTable.get(node);
    if (listeners) {
      for (var i = 0; i < listeners.length; i++) {
        if (!listeners[i].removed && listeners[i].type === type) return true;
      }
    }
    return false;
  }
  function hasListenerInAncestors(target, type) {
    for (var node = unwrap(target); node; node = node.parentNode) {
      if (hasListener(wrap(node), type)) return true;
    }
    return false;
  }
  if (OriginalEventTarget) registerWrapper(OriginalEventTarget, EventTarget);
  function wrapEventTargetMethods(constructors) {
    forwardMethodsToWrapper(constructors, methodNames);
  }
  var originalElementFromPoint = document.elementFromPoint;
  function elementFromPoint(self, document, x, y) {
    scope.renderAllPending();
    var element = wrap(originalElementFromPoint.call(unsafeUnwrap(document), x, y));
    if (!element) return null;
    var path = getEventPath(element, null);
    var idx = path.lastIndexOf(self);
    if (idx == -1) return null; else path = path.slice(0, idx);
    return eventRetargetting(path, self);
  }
  function getEventHandlerGetter(name) {
    return function() {
      var inlineEventHandlers = eventHandlersTable.get(this);
      return inlineEventHandlers && inlineEventHandlers[name] && inlineEventHandlers[name].value || null;
    };
  }
  function getEventHandlerSetter(name) {
    var eventType = name.slice(2);
    return function(value) {
      var inlineEventHandlers = eventHandlersTable.get(this);
      if (!inlineEventHandlers) {
        inlineEventHandlers = Object.create(null);
        eventHandlersTable.set(this, inlineEventHandlers);
      }
      var old = inlineEventHandlers[name];
      if (old) this.removeEventListener(eventType, old.wrapped, false);
      if (typeof value === "function") {
        var wrapped = function(e) {
          var rv = value.call(this, e);
          if (rv === false) e.preventDefault(); else if (name === "onbeforeunload" && typeof rv === "string") e.returnValue = rv;
        };
        this.addEventListener(eventType, wrapped, false);
        inlineEventHandlers[name] = {
          value: value,
          wrapped: wrapped
        };
      }
    };
  }
  scope.elementFromPoint = elementFromPoint;
  scope.getEventHandlerGetter = getEventHandlerGetter;
  scope.getEventHandlerSetter = getEventHandlerSetter;
  scope.wrapEventTargetMethods = wrapEventTargetMethods;
  scope.wrappers.BeforeUnloadEvent = BeforeUnloadEvent;
  scope.wrappers.CustomEvent = CustomEvent;
  scope.wrappers.Event = Event;
  scope.wrappers.EventTarget = EventTarget;
  scope.wrappers.FocusEvent = FocusEvent;
  scope.wrappers.MouseEvent = MouseEvent;
  scope.wrappers.UIEvent = UIEvent;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var UIEvent = scope.wrappers.UIEvent;
  var mixin = scope.mixin;
  var registerWrapper = scope.registerWrapper;
  var setWrapper = scope.setWrapper;
  var unsafeUnwrap = scope.unsafeUnwrap;
  var wrap = scope.wrap;
  var OriginalTouchEvent = window.TouchEvent;
  if (!OriginalTouchEvent) return;
  var nativeEvent;
  try {
    nativeEvent = document.createEvent("TouchEvent");
  } catch (ex) {
    return;
  }
  var nonEnumDescriptor = {
    enumerable: false
  };
  function nonEnum(obj, prop) {
    Object.defineProperty(obj, prop, nonEnumDescriptor);
  }
  function Touch(impl) {
    setWrapper(impl, this);
  }
  Touch.prototype = {
    get target() {
      return wrap(unsafeUnwrap(this).target);
    }
  };
  var descr = {
    configurable: true,
    enumerable: true,
    get: null
  };
  [ "clientX", "clientY", "screenX", "screenY", "pageX", "pageY", "identifier", "webkitRadiusX", "webkitRadiusY", "webkitRotationAngle", "webkitForce" ].forEach(function(name) {
    descr.get = function() {
      return unsafeUnwrap(this)[name];
    };
    Object.defineProperty(Touch.prototype, name, descr);
  });
  function TouchList() {
    this.length = 0;
    nonEnum(this, "length");
  }
  TouchList.prototype = {
    item: function(index) {
      return this[index];
    }
  };
  function wrapTouchList(nativeTouchList) {
    var list = new TouchList();
    for (var i = 0; i < nativeTouchList.length; i++) {
      list[i] = new Touch(nativeTouchList[i]);
    }
    list.length = i;
    return list;
  }
  function TouchEvent(impl) {
    UIEvent.call(this, impl);
  }
  TouchEvent.prototype = Object.create(UIEvent.prototype);
  mixin(TouchEvent.prototype, {
    get touches() {
      return wrapTouchList(unsafeUnwrap(this).touches);
    },
    get targetTouches() {
      return wrapTouchList(unsafeUnwrap(this).targetTouches);
    },
    get changedTouches() {
      return wrapTouchList(unsafeUnwrap(this).changedTouches);
    },
    initTouchEvent: function() {
      throw new Error("Not implemented");
    }
  });
  registerWrapper(OriginalTouchEvent, TouchEvent, nativeEvent);
  scope.wrappers.Touch = Touch;
  scope.wrappers.TouchEvent = TouchEvent;
  scope.wrappers.TouchList = TouchList;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var unsafeUnwrap = scope.unsafeUnwrap;
  var wrap = scope.wrap;
  var nonEnumDescriptor = {
    enumerable: false
  };
  function nonEnum(obj, prop) {
    Object.defineProperty(obj, prop, nonEnumDescriptor);
  }
  function NodeList() {
    this.length = 0;
    nonEnum(this, "length");
  }
  NodeList.prototype = {
    item: function(index) {
      return this[index];
    }
  };
  nonEnum(NodeList.prototype, "item");
  function wrapNodeList(list) {
    if (list == null) return list;
    var wrapperList = new NodeList();
    for (var i = 0, length = list.length; i < length; i++) {
      wrapperList[i] = wrap(list[i]);
    }
    wrapperList.length = length;
    return wrapperList;
  }
  function addWrapNodeListMethod(wrapperConstructor, name) {
    wrapperConstructor.prototype[name] = function() {
      return wrapNodeList(unsafeUnwrap(this)[name].apply(unsafeUnwrap(this), arguments));
    };
  }
  scope.wrappers.NodeList = NodeList;
  scope.addWrapNodeListMethod = addWrapNodeListMethod;
  scope.wrapNodeList = wrapNodeList;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  scope.wrapHTMLCollection = scope.wrapNodeList;
  scope.wrappers.HTMLCollection = scope.wrappers.NodeList;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var EventTarget = scope.wrappers.EventTarget;
  var NodeList = scope.wrappers.NodeList;
  var TreeScope = scope.TreeScope;
  var assert = scope.assert;
  var defineWrapGetter = scope.defineWrapGetter;
  var enqueueMutation = scope.enqueueMutation;
  var getTreeScope = scope.getTreeScope;
  var isWrapper = scope.isWrapper;
  var mixin = scope.mixin;
  var registerTransientObservers = scope.registerTransientObservers;
  var registerWrapper = scope.registerWrapper;
  var setTreeScope = scope.setTreeScope;
  var unsafeUnwrap = scope.unsafeUnwrap;
  var unwrap = scope.unwrap;
  var unwrapIfNeeded = scope.unwrapIfNeeded;
  var wrap = scope.wrap;
  var wrapIfNeeded = scope.wrapIfNeeded;
  var wrappers = scope.wrappers;
  function assertIsNodeWrapper(node) {
    assert(node instanceof Node);
  }
  function createOneElementNodeList(node) {
    var nodes = new NodeList();
    nodes[0] = node;
    nodes.length = 1;
    return nodes;
  }
  var surpressMutations = false;
  function enqueueRemovalForInsertedNodes(node, parent, nodes) {
    enqueueMutation(parent, "childList", {
      removedNodes: nodes,
      previousSibling: node.previousSibling,
      nextSibling: node.nextSibling
    });
  }
  function enqueueRemovalForInsertedDocumentFragment(df, nodes) {
    enqueueMutation(df, "childList", {
      removedNodes: nodes
    });
  }
  function collectNodes(node, parentNode, previousNode, nextNode) {
    if (node instanceof DocumentFragment) {
      var nodes = collectNodesForDocumentFragment(node);
      surpressMutations = true;
      for (var i = nodes.length - 1; i >= 0; i--) {
        node.removeChild(nodes[i]);
        nodes[i].parentNode_ = parentNode;
      }
      surpressMutations = false;
      for (var i = 0; i < nodes.length; i++) {
        nodes[i].previousSibling_ = nodes[i - 1] || previousNode;
        nodes[i].nextSibling_ = nodes[i + 1] || nextNode;
      }
      if (previousNode) previousNode.nextSibling_ = nodes[0];
      if (nextNode) nextNode.previousSibling_ = nodes[nodes.length - 1];
      return nodes;
    }
    var nodes = createOneElementNodeList(node);
    var oldParent = node.parentNode;
    if (oldParent) {
      oldParent.removeChild(node);
    }
    node.parentNode_ = parentNode;
    node.previousSibling_ = previousNode;
    node.nextSibling_ = nextNode;
    if (previousNode) previousNode.nextSibling_ = node;
    if (nextNode) nextNode.previousSibling_ = node;
    return nodes;
  }
  function collectNodesNative(node) {
    if (node instanceof DocumentFragment) return collectNodesForDocumentFragment(node);
    var nodes = createOneElementNodeList(node);
    var oldParent = node.parentNode;
    if (oldParent) enqueueRemovalForInsertedNodes(node, oldParent, nodes);
    return nodes;
  }
  function collectNodesForDocumentFragment(node) {
    var nodes = new NodeList();
    var i = 0;
    for (var child = node.firstChild; child; child = child.nextSibling) {
      nodes[i++] = child;
    }
    nodes.length = i;
    enqueueRemovalForInsertedDocumentFragment(node, nodes);
    return nodes;
  }
  function snapshotNodeList(nodeList) {
    return nodeList;
  }
  function nodeWasAdded(node, treeScope) {
    setTreeScope(node, treeScope);
    node.nodeIsInserted_();
  }
  function nodesWereAdded(nodes, parent) {
    var treeScope = getTreeScope(parent);
    for (var i = 0; i < nodes.length; i++) {
      nodeWasAdded(nodes[i], treeScope);
    }
  }
  function nodeWasRemoved(node) {
    setTreeScope(node, new TreeScope(node, null));
  }
  function nodesWereRemoved(nodes) {
    for (var i = 0; i < nodes.length; i++) {
      nodeWasRemoved(nodes[i]);
    }
  }
  function ensureSameOwnerDocument(parent, child) {
    var ownerDoc = parent.nodeType === Node.DOCUMENT_NODE ? parent : parent.ownerDocument;
    if (ownerDoc !== child.ownerDocument) ownerDoc.adoptNode(child);
  }
  function adoptNodesIfNeeded(owner, nodes) {
    if (!nodes.length) return;
    var ownerDoc = owner.ownerDocument;
    if (ownerDoc === nodes[0].ownerDocument) return;
    for (var i = 0; i < nodes.length; i++) {
      scope.adoptNodeNoRemove(nodes[i], ownerDoc);
    }
  }
  function unwrapNodesForInsertion(owner, nodes) {
    adoptNodesIfNeeded(owner, nodes);
    var length = nodes.length;
    if (length === 1) return unwrap(nodes[0]);
    var df = unwrap(owner.ownerDocument.createDocumentFragment());
    for (var i = 0; i < length; i++) {
      df.appendChild(unwrap(nodes[i]));
    }
    return df;
  }
  function clearChildNodes(wrapper) {
    if (wrapper.firstChild_ !== undefined) {
      var child = wrapper.firstChild_;
      while (child) {
        var tmp = child;
        child = child.nextSibling_;
        tmp.parentNode_ = tmp.previousSibling_ = tmp.nextSibling_ = undefined;
      }
    }
    wrapper.firstChild_ = wrapper.lastChild_ = undefined;
  }
  function removeAllChildNodes(wrapper) {
    if (wrapper.invalidateShadowRenderer()) {
      var childWrapper = wrapper.firstChild;
      while (childWrapper) {
        assert(childWrapper.parentNode === wrapper);
        var nextSibling = childWrapper.nextSibling;
        var childNode = unwrap(childWrapper);
        var parentNode = childNode.parentNode;
        if (parentNode) originalRemoveChild.call(parentNode, childNode);
        childWrapper.previousSibling_ = childWrapper.nextSibling_ = childWrapper.parentNode_ = null;
        childWrapper = nextSibling;
      }
      wrapper.firstChild_ = wrapper.lastChild_ = null;
    } else {
      var node = unwrap(wrapper);
      var child = node.firstChild;
      var nextSibling;
      while (child) {
        nextSibling = child.nextSibling;
        originalRemoveChild.call(node, child);
        child = nextSibling;
      }
    }
  }
  function invalidateParent(node) {
    var p = node.parentNode;
    return p && p.invalidateShadowRenderer();
  }
  function cleanupNodes(nodes) {
    for (var i = 0, n; i < nodes.length; i++) {
      n = nodes[i];
      n.parentNode.removeChild(n);
    }
  }
  var originalImportNode = document.importNode;
  var originalCloneNode = window.Node.prototype.cloneNode;
  function cloneNode(node, deep, opt_doc) {
    var clone;
    if (opt_doc) clone = wrap(originalImportNode.call(opt_doc, unsafeUnwrap(node), false)); else clone = wrap(originalCloneNode.call(unsafeUnwrap(node), false));
    if (deep) {
      for (var child = node.firstChild; child; child = child.nextSibling) {
        clone.appendChild(cloneNode(child, true, opt_doc));
      }
      if (node instanceof wrappers.HTMLTemplateElement) {
        var cloneContent = clone.content;
        for (var child = node.content.firstChild; child; child = child.nextSibling) {
          cloneContent.appendChild(cloneNode(child, true, opt_doc));
        }
      }
    }
    return clone;
  }
  function contains(self, child) {
    if (!child || getTreeScope(self) !== getTreeScope(child)) return false;
    for (var node = child; node; node = node.parentNode) {
      if (node === self) return true;
    }
    return false;
  }
  var OriginalNode = window.Node;
  function Node(original) {
    assert(original instanceof OriginalNode);
    EventTarget.call(this, original);
    this.parentNode_ = undefined;
    this.firstChild_ = undefined;
    this.lastChild_ = undefined;
    this.nextSibling_ = undefined;
    this.previousSibling_ = undefined;
    this.treeScope_ = undefined;
  }
  var OriginalDocumentFragment = window.DocumentFragment;
  var originalAppendChild = OriginalNode.prototype.appendChild;
  var originalCompareDocumentPosition = OriginalNode.prototype.compareDocumentPosition;
  var originalInsertBefore = OriginalNode.prototype.insertBefore;
  var originalRemoveChild = OriginalNode.prototype.removeChild;
  var originalReplaceChild = OriginalNode.prototype.replaceChild;
  var isIe = /Trident|Edge/.test(navigator.userAgent);
  var removeChildOriginalHelper = isIe ? function(parent, child) {
    try {
      originalRemoveChild.call(parent, child);
    } catch (ex) {
      if (!(parent instanceof OriginalDocumentFragment)) throw ex;
    }
  } : function(parent, child) {
    originalRemoveChild.call(parent, child);
  };
  Node.prototype = Object.create(EventTarget.prototype);
  mixin(Node.prototype, {
    appendChild: function(childWrapper) {
      return this.insertBefore(childWrapper, null);
    },
    insertBefore: function(childWrapper, refWrapper) {
      assertIsNodeWrapper(childWrapper);
      var refNode;
      if (refWrapper) {
        if (isWrapper(refWrapper)) {
          refNode = unwrap(refWrapper);
        } else {
          refNode = refWrapper;
          refWrapper = wrap(refNode);
        }
      } else {
        refWrapper = null;
        refNode = null;
      }
      refWrapper && assert(refWrapper.parentNode === this);
      var nodes;
      var previousNode = refWrapper ? refWrapper.previousSibling : this.lastChild;
      var useNative = !this.invalidateShadowRenderer() && !invalidateParent(childWrapper);
      if (useNative) nodes = collectNodesNative(childWrapper); else nodes = collectNodes(childWrapper, this, previousNode, refWrapper);
      if (useNative) {
        ensureSameOwnerDocument(this, childWrapper);
        clearChildNodes(this);
        originalInsertBefore.call(unsafeUnwrap(this), unwrap(childWrapper), refNode);
      } else {
        if (!previousNode) this.firstChild_ = nodes[0];
        if (!refWrapper) {
          this.lastChild_ = nodes[nodes.length - 1];
          if (this.firstChild_ === undefined) this.firstChild_ = this.firstChild;
        }
        var parentNode = refNode ? refNode.parentNode : unsafeUnwrap(this);
        if (parentNode) {
          originalInsertBefore.call(parentNode, unwrapNodesForInsertion(this, nodes), refNode);
        } else {
          adoptNodesIfNeeded(this, nodes);
        }
      }
      enqueueMutation(this, "childList", {
        addedNodes: nodes,
        nextSibling: refWrapper,
        previousSibling: previousNode
      });
      nodesWereAdded(nodes, this);
      return childWrapper;
    },
    removeChild: function(childWrapper) {
      assertIsNodeWrapper(childWrapper);
      if (childWrapper.parentNode !== this) {
        var found = false;
        var childNodes = this.childNodes;
        for (var ieChild = this.firstChild; ieChild; ieChild = ieChild.nextSibling) {
          if (ieChild === childWrapper) {
            found = true;
            break;
          }
        }
        if (!found) {
          throw new Error("NotFoundError");
        }
      }
      var childNode = unwrap(childWrapper);
      var childWrapperNextSibling = childWrapper.nextSibling;
      var childWrapperPreviousSibling = childWrapper.previousSibling;
      if (this.invalidateShadowRenderer()) {
        var thisFirstChild = this.firstChild;
        var thisLastChild = this.lastChild;
        var parentNode = childNode.parentNode;
        if (parentNode) removeChildOriginalHelper(parentNode, childNode);
        if (thisFirstChild === childWrapper) this.firstChild_ = childWrapperNextSibling;
        if (thisLastChild === childWrapper) this.lastChild_ = childWrapperPreviousSibling;
        if (childWrapperPreviousSibling) childWrapperPreviousSibling.nextSibling_ = childWrapperNextSibling;
        if (childWrapperNextSibling) {
          childWrapperNextSibling.previousSibling_ = childWrapperPreviousSibling;
        }
        childWrapper.previousSibling_ = childWrapper.nextSibling_ = childWrapper.parentNode_ = undefined;
      } else {
        clearChildNodes(this);
        removeChildOriginalHelper(unsafeUnwrap(this), childNode);
      }
      if (!surpressMutations) {
        enqueueMutation(this, "childList", {
          removedNodes: createOneElementNodeList(childWrapper),
          nextSibling: childWrapperNextSibling,
          previousSibling: childWrapperPreviousSibling
        });
      }
      registerTransientObservers(this, childWrapper);
      return childWrapper;
    },
    replaceChild: function(newChildWrapper, oldChildWrapper) {
      assertIsNodeWrapper(newChildWrapper);
      var oldChildNode;
      if (isWrapper(oldChildWrapper)) {
        oldChildNode = unwrap(oldChildWrapper);
      } else {
        oldChildNode = oldChildWrapper;
        oldChildWrapper = wrap(oldChildNode);
      }
      if (oldChildWrapper.parentNode !== this) {
        throw new Error("NotFoundError");
      }
      var nextNode = oldChildWrapper.nextSibling;
      var previousNode = oldChildWrapper.previousSibling;
      var nodes;
      var useNative = !this.invalidateShadowRenderer() && !invalidateParent(newChildWrapper);
      if (useNative) {
        nodes = collectNodesNative(newChildWrapper);
      } else {
        if (nextNode === newChildWrapper) nextNode = newChildWrapper.nextSibling;
        nodes = collectNodes(newChildWrapper, this, previousNode, nextNode);
      }
      if (!useNative) {
        if (this.firstChild === oldChildWrapper) this.firstChild_ = nodes[0];
        if (this.lastChild === oldChildWrapper) this.lastChild_ = nodes[nodes.length - 1];
        oldChildWrapper.previousSibling_ = oldChildWrapper.nextSibling_ = oldChildWrapper.parentNode_ = undefined;
        if (oldChildNode.parentNode) {
          originalReplaceChild.call(oldChildNode.parentNode, unwrapNodesForInsertion(this, nodes), oldChildNode);
        }
      } else {
        ensureSameOwnerDocument(this, newChildWrapper);
        clearChildNodes(this);
        originalReplaceChild.call(unsafeUnwrap(this), unwrap(newChildWrapper), oldChildNode);
      }
      enqueueMutation(this, "childList", {
        addedNodes: nodes,
        removedNodes: createOneElementNodeList(oldChildWrapper),
        nextSibling: nextNode,
        previousSibling: previousNode
      });
      nodeWasRemoved(oldChildWrapper);
      nodesWereAdded(nodes, this);
      return oldChildWrapper;
    },
    nodeIsInserted_: function() {
      for (var child = this.firstChild; child; child = child.nextSibling) {
        child.nodeIsInserted_();
      }
    },
    hasChildNodes: function() {
      return this.firstChild !== null;
    },
    get parentNode() {
      return this.parentNode_ !== undefined ? this.parentNode_ : wrap(unsafeUnwrap(this).parentNode);
    },
    get firstChild() {
      return this.firstChild_ !== undefined ? this.firstChild_ : wrap(unsafeUnwrap(this).firstChild);
    },
    get lastChild() {
      return this.lastChild_ !== undefined ? this.lastChild_ : wrap(unsafeUnwrap(this).lastChild);
    },
    get nextSibling() {
      return this.nextSibling_ !== undefined ? this.nextSibling_ : wrap(unsafeUnwrap(this).nextSibling);
    },
    get previousSibling() {
      return this.previousSibling_ !== undefined ? this.previousSibling_ : wrap(unsafeUnwrap(this).previousSibling);
    },
    get parentElement() {
      var p = this.parentNode;
      while (p && p.nodeType !== Node.ELEMENT_NODE) {
        p = p.parentNode;
      }
      return p;
    },
    get textContent() {
      var s = "";
      for (var child = this.firstChild; child; child = child.nextSibling) {
        if (child.nodeType != Node.COMMENT_NODE) {
          s += child.textContent;
        }
      }
      return s;
    },
    set textContent(textContent) {
      if (textContent == null) textContent = "";
      var removedNodes = snapshotNodeList(this.childNodes);
      if (this.invalidateShadowRenderer()) {
        removeAllChildNodes(this);
        if (textContent !== "") {
          var textNode = unsafeUnwrap(this).ownerDocument.createTextNode(textContent);
          this.appendChild(textNode);
        }
      } else {
        clearChildNodes(this);
        unsafeUnwrap(this).textContent = textContent;
      }
      var addedNodes = snapshotNodeList(this.childNodes);
      enqueueMutation(this, "childList", {
        addedNodes: addedNodes,
        removedNodes: removedNodes
      });
      nodesWereRemoved(removedNodes);
      nodesWereAdded(addedNodes, this);
    },
    get childNodes() {
      var wrapperList = new NodeList();
      var i = 0;
      for (var child = this.firstChild; child; child = child.nextSibling) {
        wrapperList[i++] = child;
      }
      wrapperList.length = i;
      return wrapperList;
    },
    cloneNode: function(deep) {
      return cloneNode(this, deep);
    },
    contains: function(child) {
      return contains(this, wrapIfNeeded(child));
    },
    compareDocumentPosition: function(otherNode) {
      return originalCompareDocumentPosition.call(unsafeUnwrap(this), unwrapIfNeeded(otherNode));
    },
    normalize: function() {
      var nodes = snapshotNodeList(this.childNodes);
      var remNodes = [];
      var s = "";
      var modNode;
      for (var i = 0, n; i < nodes.length; i++) {
        n = nodes[i];
        if (n.nodeType === Node.TEXT_NODE) {
          if (!modNode && !n.data.length) this.removeChild(n); else if (!modNode) modNode = n; else {
            s += n.data;
            remNodes.push(n);
          }
        } else {
          if (modNode && remNodes.length) {
            modNode.data += s;
            cleanupNodes(remNodes);
          }
          remNodes = [];
          s = "";
          modNode = null;
          if (n.childNodes.length) n.normalize();
        }
      }
      if (modNode && remNodes.length) {
        modNode.data += s;
        cleanupNodes(remNodes);
      }
    }
  });
  defineWrapGetter(Node, "ownerDocument");
  registerWrapper(OriginalNode, Node, document.createDocumentFragment());
  delete Node.prototype.querySelector;
  delete Node.prototype.querySelectorAll;
  Node.prototype = mixin(Object.create(EventTarget.prototype), Node.prototype);
  scope.cloneNode = cloneNode;
  scope.nodeWasAdded = nodeWasAdded;
  scope.nodeWasRemoved = nodeWasRemoved;
  scope.nodesWereAdded = nodesWereAdded;
  scope.nodesWereRemoved = nodesWereRemoved;
  scope.originalInsertBefore = originalInsertBefore;
  scope.originalRemoveChild = originalRemoveChild;
  scope.snapshotNodeList = snapshotNodeList;
  scope.wrappers.Node = Node;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var HTMLCollection = scope.wrappers.HTMLCollection;
  var NodeList = scope.wrappers.NodeList;
  var getTreeScope = scope.getTreeScope;
  var unsafeUnwrap = scope.unsafeUnwrap;
  var wrap = scope.wrap;
  var originalDocumentQuerySelector = document.querySelector;
  var originalElementQuerySelector = document.documentElement.querySelector;
  var originalDocumentQuerySelectorAll = document.querySelectorAll;
  var originalElementQuerySelectorAll = document.documentElement.querySelectorAll;
  var originalDocumentGetElementsByTagName = document.getElementsByTagName;
  var originalElementGetElementsByTagName = document.documentElement.getElementsByTagName;
  var originalDocumentGetElementsByTagNameNS = document.getElementsByTagNameNS;
  var originalElementGetElementsByTagNameNS = document.documentElement.getElementsByTagNameNS;
  var OriginalElement = window.Element;
  var OriginalDocument = window.HTMLDocument || window.Document;
  function filterNodeList(list, index, result, deep) {
    var wrappedItem = null;
    var root = null;
    for (var i = 0, length = list.length; i < length; i++) {
      wrappedItem = wrap(list[i]);
      if (!deep && (root = getTreeScope(wrappedItem).root)) {
        if (root instanceof scope.wrappers.ShadowRoot) {
          continue;
        }
      }
      result[index++] = wrappedItem;
    }
    return index;
  }
  function shimSelector(selector) {
    return String(selector).replace(/\/deep\//g, " ");
  }
  function findOne(node, selector) {
    var m, el = node.firstElementChild;
    while (el) {
      if (el.matches(selector)) return el;
      m = findOne(el, selector);
      if (m) return m;
      el = el.nextElementSibling;
    }
    return null;
  }
  function matchesSelector(el, selector) {
    return el.matches(selector);
  }
  var XHTML_NS = "http://www.w3.org/1999/xhtml";
  function matchesTagName(el, localName, localNameLowerCase) {
    var ln = el.localName;
    return ln === localName || ln === localNameLowerCase && el.namespaceURI === XHTML_NS;
  }
  function matchesEveryThing() {
    return true;
  }
  function matchesLocalNameOnly(el, ns, localName) {
    return el.localName === localName;
  }
  function matchesNameSpace(el, ns) {
    return el.namespaceURI === ns;
  }
  function matchesLocalNameNS(el, ns, localName) {
    return el.namespaceURI === ns && el.localName === localName;
  }
  function findElements(node, index, result, p, arg0, arg1) {
    var el = node.firstElementChild;
    while (el) {
      if (p(el, arg0, arg1)) result[index++] = el;
      index = findElements(el, index, result, p, arg0, arg1);
      el = el.nextElementSibling;
    }
    return index;
  }
  function querySelectorAllFiltered(p, index, result, selector, deep) {
    var target = unsafeUnwrap(this);
    var list;
    var root = getTreeScope(this).root;
    if (root instanceof scope.wrappers.ShadowRoot) {
      return findElements(this, index, result, p, selector, null);
    } else if (target instanceof OriginalElement) {
      list = originalElementQuerySelectorAll.call(target, selector);
    } else if (target instanceof OriginalDocument) {
      list = originalDocumentQuerySelectorAll.call(target, selector);
    } else {
      return findElements(this, index, result, p, selector, null);
    }
    return filterNodeList(list, index, result, deep);
  }
  var SelectorsInterface = {
    querySelector: function(selector) {
      var shimmed = shimSelector(selector);
      var deep = shimmed !== selector;
      selector = shimmed;
      var target = unsafeUnwrap(this);
      var wrappedItem;
      var root = getTreeScope(this).root;
      if (root instanceof scope.wrappers.ShadowRoot) {
        return findOne(this, selector);
      } else if (target instanceof OriginalElement) {
        wrappedItem = wrap(originalElementQuerySelector.call(target, selector));
      } else if (target instanceof OriginalDocument) {
        wrappedItem = wrap(originalDocumentQuerySelector.call(target, selector));
      } else {
        return findOne(this, selector);
      }
      if (!wrappedItem) {
        return wrappedItem;
      } else if (!deep && (root = getTreeScope(wrappedItem).root)) {
        if (root instanceof scope.wrappers.ShadowRoot) {
          return findOne(this, selector);
        }
      }
      return wrappedItem;
    },
    querySelectorAll: function(selector) {
      var shimmed = shimSelector(selector);
      var deep = shimmed !== selector;
      selector = shimmed;
      var result = new NodeList();
      result.length = querySelectorAllFiltered.call(this, matchesSelector, 0, result, selector, deep);
      return result;
    }
  };
  function getElementsByTagNameFiltered(p, index, result, localName, lowercase) {
    var target = unsafeUnwrap(this);
    var list;
    var root = getTreeScope(this).root;
    if (root instanceof scope.wrappers.ShadowRoot) {
      return findElements(this, index, result, p, localName, lowercase);
    } else if (target instanceof OriginalElement) {
      list = originalElementGetElementsByTagName.call(target, localName, lowercase);
    } else if (target instanceof OriginalDocument) {
      list = originalDocumentGetElementsByTagName.call(target, localName, lowercase);
    } else {
      return findElements(this, index, result, p, localName, lowercase);
    }
    return filterNodeList(list, index, result, false);
  }
  function getElementsByTagNameNSFiltered(p, index, result, ns, localName) {
    var target = unsafeUnwrap(this);
    var list;
    var root = getTreeScope(this).root;
    if (root instanceof scope.wrappers.ShadowRoot) {
      return findElements(this, index, result, p, ns, localName);
    } else if (target instanceof OriginalElement) {
      list = originalElementGetElementsByTagNameNS.call(target, ns, localName);
    } else if (target instanceof OriginalDocument) {
      list = originalDocumentGetElementsByTagNameNS.call(target, ns, localName);
    } else {
      return findElements(this, index, result, p, ns, localName);
    }
    return filterNodeList(list, index, result, false);
  }
  var GetElementsByInterface = {
    getElementsByTagName: function(localName) {
      var result = new HTMLCollection();
      var match = localName === "*" ? matchesEveryThing : matchesTagName;
      result.length = getElementsByTagNameFiltered.call(this, match, 0, result, localName, localName.toLowerCase());
      return result;
    },
    getElementsByClassName: function(className) {
      return this.querySelectorAll("." + className);
    },
    getElementsByTagNameNS: function(ns, localName) {
      var result = new HTMLCollection();
      var match = null;
      if (ns === "*") {
        match = localName === "*" ? matchesEveryThing : matchesLocalNameOnly;
      } else {
        match = localName === "*" ? matchesNameSpace : matchesLocalNameNS;
      }
      result.length = getElementsByTagNameNSFiltered.call(this, match, 0, result, ns || null, localName);
      return result;
    }
  };
  scope.GetElementsByInterface = GetElementsByInterface;
  scope.SelectorsInterface = SelectorsInterface;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var NodeList = scope.wrappers.NodeList;
  function forwardElement(node) {
    while (node && node.nodeType !== Node.ELEMENT_NODE) {
      node = node.nextSibling;
    }
    return node;
  }
  function backwardsElement(node) {
    while (node && node.nodeType !== Node.ELEMENT_NODE) {
      node = node.previousSibling;
    }
    return node;
  }
  var ParentNodeInterface = {
    get firstElementChild() {
      return forwardElement(this.firstChild);
    },
    get lastElementChild() {
      return backwardsElement(this.lastChild);
    },
    get childElementCount() {
      var count = 0;
      for (var child = this.firstElementChild; child; child = child.nextElementSibling) {
        count++;
      }
      return count;
    },
    get children() {
      var wrapperList = new NodeList();
      var i = 0;
      for (var child = this.firstElementChild; child; child = child.nextElementSibling) {
        wrapperList[i++] = child;
      }
      wrapperList.length = i;
      return wrapperList;
    },
    remove: function() {
      var p = this.parentNode;
      if (p) p.removeChild(this);
    }
  };
  var ChildNodeInterface = {
    get nextElementSibling() {
      return forwardElement(this.nextSibling);
    },
    get previousElementSibling() {
      return backwardsElement(this.previousSibling);
    }
  };
  scope.ChildNodeInterface = ChildNodeInterface;
  scope.ParentNodeInterface = ParentNodeInterface;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var ChildNodeInterface = scope.ChildNodeInterface;
  var Node = scope.wrappers.Node;
  var enqueueMutation = scope.enqueueMutation;
  var mixin = scope.mixin;
  var registerWrapper = scope.registerWrapper;
  var unsafeUnwrap = scope.unsafeUnwrap;
  var OriginalCharacterData = window.CharacterData;
  function CharacterData(node) {
    Node.call(this, node);
  }
  CharacterData.prototype = Object.create(Node.prototype);
  mixin(CharacterData.prototype, {
    get textContent() {
      return this.data;
    },
    set textContent(value) {
      this.data = value;
    },
    get data() {
      return unsafeUnwrap(this).data;
    },
    set data(value) {
      var oldValue = unsafeUnwrap(this).data;
      enqueueMutation(this, "characterData", {
        oldValue: oldValue
      });
      unsafeUnwrap(this).data = value;
    }
  });
  mixin(CharacterData.prototype, ChildNodeInterface);
  registerWrapper(OriginalCharacterData, CharacterData, document.createTextNode(""));
  scope.wrappers.CharacterData = CharacterData;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var CharacterData = scope.wrappers.CharacterData;
  var enqueueMutation = scope.enqueueMutation;
  var mixin = scope.mixin;
  var registerWrapper = scope.registerWrapper;
  function toUInt32(x) {
    return x >>> 0;
  }
  var OriginalText = window.Text;
  function Text(node) {
    CharacterData.call(this, node);
  }
  Text.prototype = Object.create(CharacterData.prototype);
  mixin(Text.prototype, {
    splitText: function(offset) {
      offset = toUInt32(offset);
      var s = this.data;
      if (offset > s.length) throw new Error("IndexSizeError");
      var head = s.slice(0, offset);
      var tail = s.slice(offset);
      this.data = head;
      var newTextNode = this.ownerDocument.createTextNode(tail);
      if (this.parentNode) this.parentNode.insertBefore(newTextNode, this.nextSibling);
      return newTextNode;
    }
  });
  registerWrapper(OriginalText, Text, document.createTextNode(""));
  scope.wrappers.Text = Text;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var unsafeUnwrap = scope.unsafeUnwrap;
  var enqueueMutation = scope.enqueueMutation;
  function getClass(el) {
    return unsafeUnwrap(el).getAttribute("class");
  }
  function enqueueClassAttributeChange(el, oldValue) {
    enqueueMutation(el, "attributes", {
      name: "class",
      namespace: null,
      oldValue: oldValue
    });
  }
  function invalidateClass(el) {
    scope.invalidateRendererBasedOnAttribute(el, "class");
  }
  function changeClass(tokenList, method, args) {
    var ownerElement = tokenList.ownerElement_;
    if (ownerElement == null) {
      return method.apply(tokenList, args);
    }
    var oldValue = getClass(ownerElement);
    var retv = method.apply(tokenList, args);
    if (getClass(ownerElement) !== oldValue) {
      enqueueClassAttributeChange(ownerElement, oldValue);
      invalidateClass(ownerElement);
    }
    return retv;
  }
  var oldAdd = DOMTokenList.prototype.add;
  DOMTokenList.prototype.add = function() {
    changeClass(this, oldAdd, arguments);
  };
  var oldRemove = DOMTokenList.prototype.remove;
  DOMTokenList.prototype.remove = function() {
    changeClass(this, oldRemove, arguments);
  };
  var oldToggle = DOMTokenList.prototype.toggle;
  DOMTokenList.prototype.toggle = function() {
    return changeClass(this, oldToggle, arguments);
  };
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var ChildNodeInterface = scope.ChildNodeInterface;
  var GetElementsByInterface = scope.GetElementsByInterface;
  var Node = scope.wrappers.Node;
  var ParentNodeInterface = scope.ParentNodeInterface;
  var SelectorsInterface = scope.SelectorsInterface;
  var addWrapNodeListMethod = scope.addWrapNodeListMethod;
  var enqueueMutation = scope.enqueueMutation;
  var mixin = scope.mixin;
  var oneOf = scope.oneOf;
  var registerWrapper = scope.registerWrapper;
  var unsafeUnwrap = scope.unsafeUnwrap;
  var wrappers = scope.wrappers;
  var OriginalElement = window.Element;
  var matchesNames = [ "matches", "mozMatchesSelector", "msMatchesSelector", "webkitMatchesSelector" ].filter(function(name) {
    return OriginalElement.prototype[name];
  });
  var matchesName = matchesNames[0];
  var originalMatches = OriginalElement.prototype[matchesName];
  function invalidateRendererBasedOnAttribute(element, name) {
    var p = element.parentNode;
    if (!p || !p.shadowRoot) return;
    var renderer = scope.getRendererForHost(p);
    if (renderer.dependsOnAttribute(name)) renderer.invalidate();
  }
  function enqueAttributeChange(element, name, oldValue) {
    enqueueMutation(element, "attributes", {
      name: name,
      namespace: null,
      oldValue: oldValue
    });
  }
  var classListTable = new WeakMap();
  function Element(node) {
    Node.call(this, node);
  }
  Element.prototype = Object.create(Node.prototype);
  mixin(Element.prototype, {
    createShadowRoot: function() {
      var newShadowRoot = new wrappers.ShadowRoot(this);
      unsafeUnwrap(this).polymerShadowRoot_ = newShadowRoot;
      var renderer = scope.getRendererForHost(this);
      renderer.invalidate();
      return newShadowRoot;
    },
    get shadowRoot() {
      return unsafeUnwrap(this).polymerShadowRoot_ || null;
    },
    setAttribute: function(name, value) {
      var oldValue = unsafeUnwrap(this).getAttribute(name);
      unsafeUnwrap(this).setAttribute(name, value);
      enqueAttributeChange(this, name, oldValue);
      invalidateRendererBasedOnAttribute(this, name);
    },
    removeAttribute: function(name) {
      var oldValue = unsafeUnwrap(this).getAttribute(name);
      unsafeUnwrap(this).removeAttribute(name);
      enqueAttributeChange(this, name, oldValue);
      invalidateRendererBasedOnAttribute(this, name);
    },
    matches: function(selector) {
      return originalMatches.call(unsafeUnwrap(this), selector);
    },
    get classList() {
      var list = classListTable.get(this);
      if (!list) {
        list = unsafeUnwrap(this).classList;
        list.ownerElement_ = this;
        classListTable.set(this, list);
      }
      return list;
    },
    get className() {
      return unsafeUnwrap(this).className;
    },
    set className(v) {
      this.setAttribute("class", v);
    },
    get id() {
      return unsafeUnwrap(this).id;
    },
    set id(v) {
      this.setAttribute("id", v);
    }
  });
  matchesNames.forEach(function(name) {
    if (name !== "matches") {
      Element.prototype[name] = function(selector) {
        return this.matches(selector);
      };
    }
  });
  if (OriginalElement.prototype.webkitCreateShadowRoot) {
    Element.prototype.webkitCreateShadowRoot = Element.prototype.createShadowRoot;
  }
  mixin(Element.prototype, ChildNodeInterface);
  mixin(Element.prototype, GetElementsByInterface);
  mixin(Element.prototype, ParentNodeInterface);
  mixin(Element.prototype, SelectorsInterface);
  registerWrapper(OriginalElement, Element, document.createElementNS(null, "x"));
  scope.invalidateRendererBasedOnAttribute = invalidateRendererBasedOnAttribute;
  scope.matchesNames = matchesNames;
  scope.wrappers.Element = Element;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var Element = scope.wrappers.Element;
  var defineGetter = scope.defineGetter;
  var enqueueMutation = scope.enqueueMutation;
  var mixin = scope.mixin;
  var nodesWereAdded = scope.nodesWereAdded;
  var nodesWereRemoved = scope.nodesWereRemoved;
  var registerWrapper = scope.registerWrapper;
  var snapshotNodeList = scope.snapshotNodeList;
  var unsafeUnwrap = scope.unsafeUnwrap;
  var unwrap = scope.unwrap;
  var wrap = scope.wrap;
  var wrappers = scope.wrappers;
  var escapeAttrRegExp = /[&\u00A0"]/g;
  var escapeDataRegExp = /[&\u00A0<>]/g;
  function escapeReplace(c) {
    switch (c) {
     case "&":
      return "&amp;";

     case "<":
      return "&lt;";

     case ">":
      return "&gt;";

     case '"':
      return "&quot;";

     case " ":
      return "&nbsp;";
    }
  }
  function escapeAttr(s) {
    return s.replace(escapeAttrRegExp, escapeReplace);
  }
  function escapeData(s) {
    return s.replace(escapeDataRegExp, escapeReplace);
  }
  function makeSet(arr) {
    var set = {};
    for (var i = 0; i < arr.length; i++) {
      set[arr[i]] = true;
    }
    return set;
  }
  var voidElements = makeSet([ "area", "base", "br", "col", "command", "embed", "hr", "img", "input", "keygen", "link", "meta", "param", "source", "track", "wbr" ]);
  var plaintextParents = makeSet([ "style", "script", "xmp", "iframe", "noembed", "noframes", "plaintext", "noscript" ]);
  function getOuterHTML(node, parentNode) {
    switch (node.nodeType) {
     case Node.ELEMENT_NODE:
      var tagName = node.tagName.toLowerCase();
      var s = "<" + tagName;
      var attrs = node.attributes;
      for (var i = 0, attr; attr = attrs[i]; i++) {
        s += " " + attr.name + '="' + escapeAttr(attr.value) + '"';
      }
      s += ">";
      if (voidElements[tagName]) return s;
      return s + getInnerHTML(node) + "</" + tagName + ">";

     case Node.TEXT_NODE:
      var data = node.data;
      if (parentNode && plaintextParents[parentNode.localName]) return data;
      return escapeData(data);

     case Node.COMMENT_NODE:
      return "<!--" + node.data + "-->";

     default:
      console.error(node);
      throw new Error("not implemented");
    }
  }
  function getInnerHTML(node) {
    if (node instanceof wrappers.HTMLTemplateElement) node = node.content;
    var s = "";
    for (var child = node.firstChild; child; child = child.nextSibling) {
      s += getOuterHTML(child, node);
    }
    return s;
  }
  function setInnerHTML(node, value, opt_tagName) {
    var tagName = opt_tagName || "div";
    node.textContent = "";
    var tempElement = unwrap(node.ownerDocument.createElement(tagName));
    tempElement.innerHTML = value;
    var firstChild;
    while (firstChild = tempElement.firstChild) {
      node.appendChild(wrap(firstChild));
    }
  }
  var oldIe = /MSIE/.test(navigator.userAgent);
  var OriginalHTMLElement = window.HTMLElement;
  var OriginalHTMLTemplateElement = window.HTMLTemplateElement;
  function HTMLElement(node) {
    Element.call(this, node);
  }
  HTMLElement.prototype = Object.create(Element.prototype);
  mixin(HTMLElement.prototype, {
    get innerHTML() {
      return getInnerHTML(this);
    },
    set innerHTML(value) {
      if (oldIe && plaintextParents[this.localName]) {
        this.textContent = value;
        return;
      }
      var removedNodes = snapshotNodeList(this.childNodes);
      if (this.invalidateShadowRenderer()) {
        if (this instanceof wrappers.HTMLTemplateElement) setInnerHTML(this.content, value); else setInnerHTML(this, value, this.tagName);
      } else if (!OriginalHTMLTemplateElement && this instanceof wrappers.HTMLTemplateElement) {
        setInnerHTML(this.content, value);
      } else {
        unsafeUnwrap(this).innerHTML = value;
      }
      var addedNodes = snapshotNodeList(this.childNodes);
      enqueueMutation(this, "childList", {
        addedNodes: addedNodes,
        removedNodes: removedNodes
      });
      nodesWereRemoved(removedNodes);
      nodesWereAdded(addedNodes, this);
    },
    get outerHTML() {
      return getOuterHTML(this, this.parentNode);
    },
    set outerHTML(value) {
      var p = this.parentNode;
      if (p) {
        p.invalidateShadowRenderer();
        var df = frag(p, value);
        p.replaceChild(df, this);
      }
    },
    insertAdjacentHTML: function(position, text) {
      var contextElement, refNode;
      switch (String(position).toLowerCase()) {
       case "beforebegin":
        contextElement = this.parentNode;
        refNode = this;
        break;

       case "afterend":
        contextElement = this.parentNode;
        refNode = this.nextSibling;
        break;

       case "afterbegin":
        contextElement = this;
        refNode = this.firstChild;
        break;

       case "beforeend":
        contextElement = this;
        refNode = null;
        break;

       default:
        return;
      }
      var df = frag(contextElement, text);
      contextElement.insertBefore(df, refNode);
    },
    get hidden() {
      return this.hasAttribute("hidden");
    },
    set hidden(v) {
      if (v) {
        this.setAttribute("hidden", "");
      } else {
        this.removeAttribute("hidden");
      }
    }
  });
  function frag(contextElement, html) {
    var p = unwrap(contextElement.cloneNode(false));
    p.innerHTML = html;
    var df = unwrap(document.createDocumentFragment());
    var c;
    while (c = p.firstChild) {
      df.appendChild(c);
    }
    return wrap(df);
  }
  function getter(name) {
    return function() {
      scope.renderAllPending();
      return unsafeUnwrap(this)[name];
    };
  }
  function getterRequiresRendering(name) {
    defineGetter(HTMLElement, name, getter(name));
  }
  [ "clientHeight", "clientLeft", "clientTop", "clientWidth", "offsetHeight", "offsetLeft", "offsetTop", "offsetWidth", "scrollHeight", "scrollWidth" ].forEach(getterRequiresRendering);
  function getterAndSetterRequiresRendering(name) {
    Object.defineProperty(HTMLElement.prototype, name, {
      get: getter(name),
      set: function(v) {
        scope.renderAllPending();
        unsafeUnwrap(this)[name] = v;
      },
      configurable: true,
      enumerable: true
    });
  }
  [ "scrollLeft", "scrollTop" ].forEach(getterAndSetterRequiresRendering);
  function methodRequiresRendering(name) {
    Object.defineProperty(HTMLElement.prototype, name, {
      value: function() {
        scope.renderAllPending();
        return unsafeUnwrap(this)[name].apply(unsafeUnwrap(this), arguments);
      },
      configurable: true,
      enumerable: true
    });
  }
  [ "getBoundingClientRect", "getClientRects", "scrollIntoView" ].forEach(methodRequiresRendering);
  registerWrapper(OriginalHTMLElement, HTMLElement, document.createElement("b"));
  scope.wrappers.HTMLElement = HTMLElement;
  scope.getInnerHTML = getInnerHTML;
  scope.setInnerHTML = setInnerHTML;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var HTMLElement = scope.wrappers.HTMLElement;
  var mixin = scope.mixin;
  var registerWrapper = scope.registerWrapper;
  var unsafeUnwrap = scope.unsafeUnwrap;
  var wrap = scope.wrap;
  var OriginalHTMLCanvasElement = window.HTMLCanvasElement;
  function HTMLCanvasElement(node) {
    HTMLElement.call(this, node);
  }
  HTMLCanvasElement.prototype = Object.create(HTMLElement.prototype);
  mixin(HTMLCanvasElement.prototype, {
    getContext: function() {
      var context = unsafeUnwrap(this).getContext.apply(unsafeUnwrap(this), arguments);
      return context && wrap(context);
    }
  });
  registerWrapper(OriginalHTMLCanvasElement, HTMLCanvasElement, document.createElement("canvas"));
  scope.wrappers.HTMLCanvasElement = HTMLCanvasElement;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var HTMLElement = scope.wrappers.HTMLElement;
  var mixin = scope.mixin;
  var registerWrapper = scope.registerWrapper;
  var OriginalHTMLContentElement = window.HTMLContentElement;
  function HTMLContentElement(node) {
    HTMLElement.call(this, node);
  }
  HTMLContentElement.prototype = Object.create(HTMLElement.prototype);
  mixin(HTMLContentElement.prototype, {
    constructor: HTMLContentElement,
    get select() {
      return this.getAttribute("select");
    },
    set select(value) {
      this.setAttribute("select", value);
    },
    setAttribute: function(n, v) {
      HTMLElement.prototype.setAttribute.call(this, n, v);
      if (String(n).toLowerCase() === "select") this.invalidateShadowRenderer(true);
    }
  });
  if (OriginalHTMLContentElement) registerWrapper(OriginalHTMLContentElement, HTMLContentElement);
  scope.wrappers.HTMLContentElement = HTMLContentElement;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var HTMLElement = scope.wrappers.HTMLElement;
  var mixin = scope.mixin;
  var registerWrapper = scope.registerWrapper;
  var wrapHTMLCollection = scope.wrapHTMLCollection;
  var unwrap = scope.unwrap;
  var OriginalHTMLFormElement = window.HTMLFormElement;
  function HTMLFormElement(node) {
    HTMLElement.call(this, node);
  }
  HTMLFormElement.prototype = Object.create(HTMLElement.prototype);
  mixin(HTMLFormElement.prototype, {
    get elements() {
      return wrapHTMLCollection(unwrap(this).elements);
    }
  });
  registerWrapper(OriginalHTMLFormElement, HTMLFormElement, document.createElement("form"));
  scope.wrappers.HTMLFormElement = HTMLFormElement;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var HTMLElement = scope.wrappers.HTMLElement;
  var registerWrapper = scope.registerWrapper;
  var unwrap = scope.unwrap;
  var rewrap = scope.rewrap;
  var OriginalHTMLImageElement = window.HTMLImageElement;
  function HTMLImageElement(node) {
    HTMLElement.call(this, node);
  }
  HTMLImageElement.prototype = Object.create(HTMLElement.prototype);
  registerWrapper(OriginalHTMLImageElement, HTMLImageElement, document.createElement("img"));
  function Image(width, height) {
    if (!(this instanceof Image)) {
      throw new TypeError("DOM object constructor cannot be called as a function.");
    }
    var node = unwrap(document.createElement("img"));
    HTMLElement.call(this, node);
    rewrap(node, this);
    if (width !== undefined) node.width = width;
    if (height !== undefined) node.height = height;
  }
  Image.prototype = HTMLImageElement.prototype;
  scope.wrappers.HTMLImageElement = HTMLImageElement;
  scope.wrappers.Image = Image;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var HTMLElement = scope.wrappers.HTMLElement;
  var mixin = scope.mixin;
  var NodeList = scope.wrappers.NodeList;
  var registerWrapper = scope.registerWrapper;
  var OriginalHTMLShadowElement = window.HTMLShadowElement;
  function HTMLShadowElement(node) {
    HTMLElement.call(this, node);
  }
  HTMLShadowElement.prototype = Object.create(HTMLElement.prototype);
  HTMLShadowElement.prototype.constructor = HTMLShadowElement;
  if (OriginalHTMLShadowElement) registerWrapper(OriginalHTMLShadowElement, HTMLShadowElement);
  scope.wrappers.HTMLShadowElement = HTMLShadowElement;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var HTMLElement = scope.wrappers.HTMLElement;
  var mixin = scope.mixin;
  var registerWrapper = scope.registerWrapper;
  var unsafeUnwrap = scope.unsafeUnwrap;
  var unwrap = scope.unwrap;
  var wrap = scope.wrap;
  var contentTable = new WeakMap();
  var templateContentsOwnerTable = new WeakMap();
  function getTemplateContentsOwner(doc) {
    if (!doc.defaultView) return doc;
    var d = templateContentsOwnerTable.get(doc);
    if (!d) {
      d = doc.implementation.createHTMLDocument("");
      while (d.lastChild) {
        d.removeChild(d.lastChild);
      }
      templateContentsOwnerTable.set(doc, d);
    }
    return d;
  }
  function extractContent(templateElement) {
    var doc = getTemplateContentsOwner(templateElement.ownerDocument);
    var df = unwrap(doc.createDocumentFragment());
    var child;
    while (child = templateElement.firstChild) {
      df.appendChild(child);
    }
    return df;
  }
  var OriginalHTMLTemplateElement = window.HTMLTemplateElement;
  function HTMLTemplateElement(node) {
    HTMLElement.call(this, node);
    if (!OriginalHTMLTemplateElement) {
      var content = extractContent(node);
      contentTable.set(this, wrap(content));
    }
  }
  HTMLTemplateElement.prototype = Object.create(HTMLElement.prototype);
  mixin(HTMLTemplateElement.prototype, {
    constructor: HTMLTemplateElement,
    get content() {
      if (OriginalHTMLTemplateElement) return wrap(unsafeUnwrap(this).content);
      return contentTable.get(this);
    }
  });
  if (OriginalHTMLTemplateElement) registerWrapper(OriginalHTMLTemplateElement, HTMLTemplateElement);
  scope.wrappers.HTMLTemplateElement = HTMLTemplateElement;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var HTMLElement = scope.wrappers.HTMLElement;
  var registerWrapper = scope.registerWrapper;
  var OriginalHTMLMediaElement = window.HTMLMediaElement;
  if (!OriginalHTMLMediaElement) return;
  function HTMLMediaElement(node) {
    HTMLElement.call(this, node);
  }
  HTMLMediaElement.prototype = Object.create(HTMLElement.prototype);
  registerWrapper(OriginalHTMLMediaElement, HTMLMediaElement, document.createElement("audio"));
  scope.wrappers.HTMLMediaElement = HTMLMediaElement;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var HTMLMediaElement = scope.wrappers.HTMLMediaElement;
  var registerWrapper = scope.registerWrapper;
  var unwrap = scope.unwrap;
  var rewrap = scope.rewrap;
  var OriginalHTMLAudioElement = window.HTMLAudioElement;
  if (!OriginalHTMLAudioElement) return;
  function HTMLAudioElement(node) {
    HTMLMediaElement.call(this, node);
  }
  HTMLAudioElement.prototype = Object.create(HTMLMediaElement.prototype);
  registerWrapper(OriginalHTMLAudioElement, HTMLAudioElement, document.createElement("audio"));
  function Audio(src) {
    if (!(this instanceof Audio)) {
      throw new TypeError("DOM object constructor cannot be called as a function.");
    }
    var node = unwrap(document.createElement("audio"));
    HTMLMediaElement.call(this, node);
    rewrap(node, this);
    node.setAttribute("preload", "auto");
    if (src !== undefined) node.setAttribute("src", src);
  }
  Audio.prototype = HTMLAudioElement.prototype;
  scope.wrappers.HTMLAudioElement = HTMLAudioElement;
  scope.wrappers.Audio = Audio;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var HTMLElement = scope.wrappers.HTMLElement;
  var mixin = scope.mixin;
  var registerWrapper = scope.registerWrapper;
  var rewrap = scope.rewrap;
  var unwrap = scope.unwrap;
  var wrap = scope.wrap;
  var OriginalHTMLOptionElement = window.HTMLOptionElement;
  function trimText(s) {
    return s.replace(/\s+/g, " ").trim();
  }
  function HTMLOptionElement(node) {
    HTMLElement.call(this, node);
  }
  HTMLOptionElement.prototype = Object.create(HTMLElement.prototype);
  mixin(HTMLOptionElement.prototype, {
    get text() {
      return trimText(this.textContent);
    },
    set text(value) {
      this.textContent = trimText(String(value));
    },
    get form() {
      return wrap(unwrap(this).form);
    }
  });
  registerWrapper(OriginalHTMLOptionElement, HTMLOptionElement, document.createElement("option"));
  function Option(text, value, defaultSelected, selected) {
    if (!(this instanceof Option)) {
      throw new TypeError("DOM object constructor cannot be called as a function.");
    }
    var node = unwrap(document.createElement("option"));
    HTMLElement.call(this, node);
    rewrap(node, this);
    if (text !== undefined) node.text = text;
    if (value !== undefined) node.setAttribute("value", value);
    if (defaultSelected === true) node.setAttribute("selected", "");
    node.selected = selected === true;
  }
  Option.prototype = HTMLOptionElement.prototype;
  scope.wrappers.HTMLOptionElement = HTMLOptionElement;
  scope.wrappers.Option = Option;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var HTMLElement = scope.wrappers.HTMLElement;
  var mixin = scope.mixin;
  var registerWrapper = scope.registerWrapper;
  var unwrap = scope.unwrap;
  var wrap = scope.wrap;
  var OriginalHTMLSelectElement = window.HTMLSelectElement;
  function HTMLSelectElement(node) {
    HTMLElement.call(this, node);
  }
  HTMLSelectElement.prototype = Object.create(HTMLElement.prototype);
  mixin(HTMLSelectElement.prototype, {
    add: function(element, before) {
      if (typeof before === "object") before = unwrap(before);
      unwrap(this).add(unwrap(element), before);
    },
    remove: function(indexOrNode) {
      if (indexOrNode === undefined) {
        HTMLElement.prototype.remove.call(this);
        return;
      }
      if (typeof indexOrNode === "object") indexOrNode = unwrap(indexOrNode);
      unwrap(this).remove(indexOrNode);
    },
    get form() {
      return wrap(unwrap(this).form);
    }
  });
  registerWrapper(OriginalHTMLSelectElement, HTMLSelectElement, document.createElement("select"));
  scope.wrappers.HTMLSelectElement = HTMLSelectElement;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var HTMLElement = scope.wrappers.HTMLElement;
  var mixin = scope.mixin;
  var registerWrapper = scope.registerWrapper;
  var unwrap = scope.unwrap;
  var wrap = scope.wrap;
  var wrapHTMLCollection = scope.wrapHTMLCollection;
  var OriginalHTMLTableElement = window.HTMLTableElement;
  function HTMLTableElement(node) {
    HTMLElement.call(this, node);
  }
  HTMLTableElement.prototype = Object.create(HTMLElement.prototype);
  mixin(HTMLTableElement.prototype, {
    get caption() {
      return wrap(unwrap(this).caption);
    },
    createCaption: function() {
      return wrap(unwrap(this).createCaption());
    },
    get tHead() {
      return wrap(unwrap(this).tHead);
    },
    createTHead: function() {
      return wrap(unwrap(this).createTHead());
    },
    createTFoot: function() {
      return wrap(unwrap(this).createTFoot());
    },
    get tFoot() {
      return wrap(unwrap(this).tFoot);
    },
    get tBodies() {
      return wrapHTMLCollection(unwrap(this).tBodies);
    },
    createTBody: function() {
      return wrap(unwrap(this).createTBody());
    },
    get rows() {
      return wrapHTMLCollection(unwrap(this).rows);
    },
    insertRow: function(index) {
      return wrap(unwrap(this).insertRow(index));
    }
  });
  registerWrapper(OriginalHTMLTableElement, HTMLTableElement, document.createElement("table"));
  scope.wrappers.HTMLTableElement = HTMLTableElement;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var HTMLElement = scope.wrappers.HTMLElement;
  var mixin = scope.mixin;
  var registerWrapper = scope.registerWrapper;
  var wrapHTMLCollection = scope.wrapHTMLCollection;
  var unwrap = scope.unwrap;
  var wrap = scope.wrap;
  var OriginalHTMLTableSectionElement = window.HTMLTableSectionElement;
  function HTMLTableSectionElement(node) {
    HTMLElement.call(this, node);
  }
  HTMLTableSectionElement.prototype = Object.create(HTMLElement.prototype);
  mixin(HTMLTableSectionElement.prototype, {
    constructor: HTMLTableSectionElement,
    get rows() {
      return wrapHTMLCollection(unwrap(this).rows);
    },
    insertRow: function(index) {
      return wrap(unwrap(this).insertRow(index));
    }
  });
  registerWrapper(OriginalHTMLTableSectionElement, HTMLTableSectionElement, document.createElement("thead"));
  scope.wrappers.HTMLTableSectionElement = HTMLTableSectionElement;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var HTMLElement = scope.wrappers.HTMLElement;
  var mixin = scope.mixin;
  var registerWrapper = scope.registerWrapper;
  var wrapHTMLCollection = scope.wrapHTMLCollection;
  var unwrap = scope.unwrap;
  var wrap = scope.wrap;
  var OriginalHTMLTableRowElement = window.HTMLTableRowElement;
  function HTMLTableRowElement(node) {
    HTMLElement.call(this, node);
  }
  HTMLTableRowElement.prototype = Object.create(HTMLElement.prototype);
  mixin(HTMLTableRowElement.prototype, {
    get cells() {
      return wrapHTMLCollection(unwrap(this).cells);
    },
    insertCell: function(index) {
      return wrap(unwrap(this).insertCell(index));
    }
  });
  registerWrapper(OriginalHTMLTableRowElement, HTMLTableRowElement, document.createElement("tr"));
  scope.wrappers.HTMLTableRowElement = HTMLTableRowElement;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var HTMLContentElement = scope.wrappers.HTMLContentElement;
  var HTMLElement = scope.wrappers.HTMLElement;
  var HTMLShadowElement = scope.wrappers.HTMLShadowElement;
  var HTMLTemplateElement = scope.wrappers.HTMLTemplateElement;
  var mixin = scope.mixin;
  var registerWrapper = scope.registerWrapper;
  var OriginalHTMLUnknownElement = window.HTMLUnknownElement;
  function HTMLUnknownElement(node) {
    switch (node.localName) {
     case "content":
      return new HTMLContentElement(node);

     case "shadow":
      return new HTMLShadowElement(node);

     case "template":
      return new HTMLTemplateElement(node);
    }
    HTMLElement.call(this, node);
  }
  HTMLUnknownElement.prototype = Object.create(HTMLElement.prototype);
  registerWrapper(OriginalHTMLUnknownElement, HTMLUnknownElement);
  scope.wrappers.HTMLUnknownElement = HTMLUnknownElement;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var Element = scope.wrappers.Element;
  var HTMLElement = scope.wrappers.HTMLElement;
  var registerObject = scope.registerObject;
  var SVG_NS = "http://www.w3.org/2000/svg";
  var svgTitleElement = document.createElementNS(SVG_NS, "title");
  var SVGTitleElement = registerObject(svgTitleElement);
  var SVGElement = Object.getPrototypeOf(SVGTitleElement.prototype).constructor;
  if (!("classList" in svgTitleElement)) {
    var descr = Object.getOwnPropertyDescriptor(Element.prototype, "classList");
    Object.defineProperty(HTMLElement.prototype, "classList", descr);
    delete Element.prototype.classList;
  }
  scope.wrappers.SVGElement = SVGElement;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var mixin = scope.mixin;
  var registerWrapper = scope.registerWrapper;
  var unwrap = scope.unwrap;
  var wrap = scope.wrap;
  var OriginalSVGUseElement = window.SVGUseElement;
  var SVG_NS = "http://www.w3.org/2000/svg";
  var gWrapper = wrap(document.createElementNS(SVG_NS, "g"));
  var useElement = document.createElementNS(SVG_NS, "use");
  var SVGGElement = gWrapper.constructor;
  var parentInterfacePrototype = Object.getPrototypeOf(SVGGElement.prototype);
  var parentInterface = parentInterfacePrototype.constructor;
  function SVGUseElement(impl) {
    parentInterface.call(this, impl);
  }
  SVGUseElement.prototype = Object.create(parentInterfacePrototype);
  if ("instanceRoot" in useElement) {
    mixin(SVGUseElement.prototype, {
      get instanceRoot() {
        return wrap(unwrap(this).instanceRoot);
      },
      get animatedInstanceRoot() {
        return wrap(unwrap(this).animatedInstanceRoot);
      }
    });
  }
  registerWrapper(OriginalSVGUseElement, SVGUseElement, useElement);
  scope.wrappers.SVGUseElement = SVGUseElement;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var EventTarget = scope.wrappers.EventTarget;
  var mixin = scope.mixin;
  var registerWrapper = scope.registerWrapper;
  var unsafeUnwrap = scope.unsafeUnwrap;
  var wrap = scope.wrap;
  var OriginalSVGElementInstance = window.SVGElementInstance;
  if (!OriginalSVGElementInstance) return;
  function SVGElementInstance(impl) {
    EventTarget.call(this, impl);
  }
  SVGElementInstance.prototype = Object.create(EventTarget.prototype);
  mixin(SVGElementInstance.prototype, {
    get correspondingElement() {
      return wrap(unsafeUnwrap(this).correspondingElement);
    },
    get correspondingUseElement() {
      return wrap(unsafeUnwrap(this).correspondingUseElement);
    },
    get parentNode() {
      return wrap(unsafeUnwrap(this).parentNode);
    },
    get childNodes() {
      throw new Error("Not implemented");
    },
    get firstChild() {
      return wrap(unsafeUnwrap(this).firstChild);
    },
    get lastChild() {
      return wrap(unsafeUnwrap(this).lastChild);
    },
    get previousSibling() {
      return wrap(unsafeUnwrap(this).previousSibling);
    },
    get nextSibling() {
      return wrap(unsafeUnwrap(this).nextSibling);
    }
  });
  registerWrapper(OriginalSVGElementInstance, SVGElementInstance);
  scope.wrappers.SVGElementInstance = SVGElementInstance;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var mixin = scope.mixin;
  var registerWrapper = scope.registerWrapper;
  var setWrapper = scope.setWrapper;
  var unsafeUnwrap = scope.unsafeUnwrap;
  var unwrap = scope.unwrap;
  var unwrapIfNeeded = scope.unwrapIfNeeded;
  var wrap = scope.wrap;
  var OriginalCanvasRenderingContext2D = window.CanvasRenderingContext2D;
  function CanvasRenderingContext2D(impl) {
    setWrapper(impl, this);
  }
  mixin(CanvasRenderingContext2D.prototype, {
    get canvas() {
      return wrap(unsafeUnwrap(this).canvas);
    },
    drawImage: function() {
      arguments[0] = unwrapIfNeeded(arguments[0]);
      unsafeUnwrap(this).drawImage.apply(unsafeUnwrap(this), arguments);
    },
    createPattern: function() {
      arguments[0] = unwrap(arguments[0]);
      return unsafeUnwrap(this).createPattern.apply(unsafeUnwrap(this), arguments);
    }
  });
  registerWrapper(OriginalCanvasRenderingContext2D, CanvasRenderingContext2D, document.createElement("canvas").getContext("2d"));
  scope.wrappers.CanvasRenderingContext2D = CanvasRenderingContext2D;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var mixin = scope.mixin;
  var registerWrapper = scope.registerWrapper;
  var setWrapper = scope.setWrapper;
  var unsafeUnwrap = scope.unsafeUnwrap;
  var unwrapIfNeeded = scope.unwrapIfNeeded;
  var wrap = scope.wrap;
  var OriginalWebGLRenderingContext = window.WebGLRenderingContext;
  if (!OriginalWebGLRenderingContext) return;
  function WebGLRenderingContext(impl) {
    setWrapper(impl, this);
  }
  mixin(WebGLRenderingContext.prototype, {
    get canvas() {
      return wrap(unsafeUnwrap(this).canvas);
    },
    texImage2D: function() {
      arguments[5] = unwrapIfNeeded(arguments[5]);
      unsafeUnwrap(this).texImage2D.apply(unsafeUnwrap(this), arguments);
    },
    texSubImage2D: function() {
      arguments[6] = unwrapIfNeeded(arguments[6]);
      unsafeUnwrap(this).texSubImage2D.apply(unsafeUnwrap(this), arguments);
    }
  });
  var instanceProperties = /WebKit/.test(navigator.userAgent) ? {
    drawingBufferHeight: null,
    drawingBufferWidth: null
  } : {};
  registerWrapper(OriginalWebGLRenderingContext, WebGLRenderingContext, instanceProperties);
  scope.wrappers.WebGLRenderingContext = WebGLRenderingContext;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var registerWrapper = scope.registerWrapper;
  var setWrapper = scope.setWrapper;
  var unsafeUnwrap = scope.unsafeUnwrap;
  var unwrap = scope.unwrap;
  var unwrapIfNeeded = scope.unwrapIfNeeded;
  var wrap = scope.wrap;
  var OriginalRange = window.Range;
  function Range(impl) {
    setWrapper(impl, this);
  }
  Range.prototype = {
    get startContainer() {
      return wrap(unsafeUnwrap(this).startContainer);
    },
    get endContainer() {
      return wrap(unsafeUnwrap(this).endContainer);
    },
    get commonAncestorContainer() {
      return wrap(unsafeUnwrap(this).commonAncestorContainer);
    },
    setStart: function(refNode, offset) {
      unsafeUnwrap(this).setStart(unwrapIfNeeded(refNode), offset);
    },
    setEnd: function(refNode, offset) {
      unsafeUnwrap(this).setEnd(unwrapIfNeeded(refNode), offset);
    },
    setStartBefore: function(refNode) {
      unsafeUnwrap(this).setStartBefore(unwrapIfNeeded(refNode));
    },
    setStartAfter: function(refNode) {
      unsafeUnwrap(this).setStartAfter(unwrapIfNeeded(refNode));
    },
    setEndBefore: function(refNode) {
      unsafeUnwrap(this).setEndBefore(unwrapIfNeeded(refNode));
    },
    setEndAfter: function(refNode) {
      unsafeUnwrap(this).setEndAfter(unwrapIfNeeded(refNode));
    },
    selectNode: function(refNode) {
      unsafeUnwrap(this).selectNode(unwrapIfNeeded(refNode));
    },
    selectNodeContents: function(refNode) {
      unsafeUnwrap(this).selectNodeContents(unwrapIfNeeded(refNode));
    },
    compareBoundaryPoints: function(how, sourceRange) {
      return unsafeUnwrap(this).compareBoundaryPoints(how, unwrap(sourceRange));
    },
    extractContents: function() {
      return wrap(unsafeUnwrap(this).extractContents());
    },
    cloneContents: function() {
      return wrap(unsafeUnwrap(this).cloneContents());
    },
    insertNode: function(node) {
      unsafeUnwrap(this).insertNode(unwrapIfNeeded(node));
    },
    surroundContents: function(newParent) {
      unsafeUnwrap(this).surroundContents(unwrapIfNeeded(newParent));
    },
    cloneRange: function() {
      return wrap(unsafeUnwrap(this).cloneRange());
    },
    isPointInRange: function(node, offset) {
      return unsafeUnwrap(this).isPointInRange(unwrapIfNeeded(node), offset);
    },
    comparePoint: function(node, offset) {
      return unsafeUnwrap(this).comparePoint(unwrapIfNeeded(node), offset);
    },
    intersectsNode: function(node) {
      return unsafeUnwrap(this).intersectsNode(unwrapIfNeeded(node));
    },
    toString: function() {
      return unsafeUnwrap(this).toString();
    }
  };
  if (OriginalRange.prototype.createContextualFragment) {
    Range.prototype.createContextualFragment = function(html) {
      return wrap(unsafeUnwrap(this).createContextualFragment(html));
    };
  }
  registerWrapper(window.Range, Range, document.createRange());
  scope.wrappers.Range = Range;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var GetElementsByInterface = scope.GetElementsByInterface;
  var ParentNodeInterface = scope.ParentNodeInterface;
  var SelectorsInterface = scope.SelectorsInterface;
  var mixin = scope.mixin;
  var registerObject = scope.registerObject;
  var DocumentFragment = registerObject(document.createDocumentFragment());
  mixin(DocumentFragment.prototype, ParentNodeInterface);
  mixin(DocumentFragment.prototype, SelectorsInterface);
  mixin(DocumentFragment.prototype, GetElementsByInterface);
  var Comment = registerObject(document.createComment(""));
  scope.wrappers.Comment = Comment;
  scope.wrappers.DocumentFragment = DocumentFragment;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var DocumentFragment = scope.wrappers.DocumentFragment;
  var TreeScope = scope.TreeScope;
  var elementFromPoint = scope.elementFromPoint;
  var getInnerHTML = scope.getInnerHTML;
  var getTreeScope = scope.getTreeScope;
  var mixin = scope.mixin;
  var rewrap = scope.rewrap;
  var setInnerHTML = scope.setInnerHTML;
  var unsafeUnwrap = scope.unsafeUnwrap;
  var unwrap = scope.unwrap;
  var shadowHostTable = new WeakMap();
  var nextOlderShadowTreeTable = new WeakMap();
  var spaceCharRe = /[ \t\n\r\f]/;
  function ShadowRoot(hostWrapper) {
    var node = unwrap(unsafeUnwrap(hostWrapper).ownerDocument.createDocumentFragment());
    DocumentFragment.call(this, node);
    rewrap(node, this);
    var oldShadowRoot = hostWrapper.shadowRoot;
    nextOlderShadowTreeTable.set(this, oldShadowRoot);
    this.treeScope_ = new TreeScope(this, getTreeScope(oldShadowRoot || hostWrapper));
    shadowHostTable.set(this, hostWrapper);
  }
  ShadowRoot.prototype = Object.create(DocumentFragment.prototype);
  mixin(ShadowRoot.prototype, {
    constructor: ShadowRoot,
    get innerHTML() {
      return getInnerHTML(this);
    },
    set innerHTML(value) {
      setInnerHTML(this, value);
      this.invalidateShadowRenderer();
    },
    get olderShadowRoot() {
      return nextOlderShadowTreeTable.get(this) || null;
    },
    get host() {
      return shadowHostTable.get(this) || null;
    },
    invalidateShadowRenderer: function() {
      return shadowHostTable.get(this).invalidateShadowRenderer();
    },
    elementFromPoint: function(x, y) {
      return elementFromPoint(this, this.ownerDocument, x, y);
    },
    getElementById: function(id) {
      if (spaceCharRe.test(id)) return null;
      return this.querySelector('[id="' + id + '"]');
    }
  });
  scope.wrappers.ShadowRoot = ShadowRoot;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var Element = scope.wrappers.Element;
  var HTMLContentElement = scope.wrappers.HTMLContentElement;
  var HTMLShadowElement = scope.wrappers.HTMLShadowElement;
  var Node = scope.wrappers.Node;
  var ShadowRoot = scope.wrappers.ShadowRoot;
  var assert = scope.assert;
  var getTreeScope = scope.getTreeScope;
  var mixin = scope.mixin;
  var oneOf = scope.oneOf;
  var unsafeUnwrap = scope.unsafeUnwrap;
  var unwrap = scope.unwrap;
  var wrap = scope.wrap;
  var ArraySplice = scope.ArraySplice;
  function updateWrapperUpAndSideways(wrapper) {
    wrapper.previousSibling_ = wrapper.previousSibling;
    wrapper.nextSibling_ = wrapper.nextSibling;
    wrapper.parentNode_ = wrapper.parentNode;
  }
  function updateWrapperDown(wrapper) {
    wrapper.firstChild_ = wrapper.firstChild;
    wrapper.lastChild_ = wrapper.lastChild;
  }
  function updateAllChildNodes(parentNodeWrapper) {
    assert(parentNodeWrapper instanceof Node);
    for (var childWrapper = parentNodeWrapper.firstChild; childWrapper; childWrapper = childWrapper.nextSibling) {
      updateWrapperUpAndSideways(childWrapper);
    }
    updateWrapperDown(parentNodeWrapper);
  }
  function insertBefore(parentNodeWrapper, newChildWrapper, refChildWrapper) {
    var parentNode = unwrap(parentNodeWrapper);
    var newChild = unwrap(newChildWrapper);
    var refChild = refChildWrapper ? unwrap(refChildWrapper) : null;
    remove(newChildWrapper);
    updateWrapperUpAndSideways(newChildWrapper);
    if (!refChildWrapper) {
      parentNodeWrapper.lastChild_ = parentNodeWrapper.lastChild;
      if (parentNodeWrapper.lastChild === parentNodeWrapper.firstChild) parentNodeWrapper.firstChild_ = parentNodeWrapper.firstChild;
      var lastChildWrapper = wrap(parentNode.lastChild);
      if (lastChildWrapper) lastChildWrapper.nextSibling_ = lastChildWrapper.nextSibling;
    } else {
      if (parentNodeWrapper.firstChild === refChildWrapper) parentNodeWrapper.firstChild_ = refChildWrapper;
      refChildWrapper.previousSibling_ = refChildWrapper.previousSibling;
    }
    scope.originalInsertBefore.call(parentNode, newChild, refChild);
  }
  function remove(nodeWrapper) {
    var node = unwrap(nodeWrapper);
    var parentNode = node.parentNode;
    if (!parentNode) return;
    var parentNodeWrapper = wrap(parentNode);
    updateWrapperUpAndSideways(nodeWrapper);
    if (nodeWrapper.previousSibling) nodeWrapper.previousSibling.nextSibling_ = nodeWrapper;
    if (nodeWrapper.nextSibling) nodeWrapper.nextSibling.previousSibling_ = nodeWrapper;
    if (parentNodeWrapper.lastChild === nodeWrapper) parentNodeWrapper.lastChild_ = nodeWrapper;
    if (parentNodeWrapper.firstChild === nodeWrapper) parentNodeWrapper.firstChild_ = nodeWrapper;
    scope.originalRemoveChild.call(parentNode, node);
  }
  var distributedNodesTable = new WeakMap();
  var destinationInsertionPointsTable = new WeakMap();
  var rendererForHostTable = new WeakMap();
  function resetDistributedNodes(insertionPoint) {
    distributedNodesTable.set(insertionPoint, []);
  }
  function getDistributedNodes(insertionPoint) {
    var rv = distributedNodesTable.get(insertionPoint);
    if (!rv) distributedNodesTable.set(insertionPoint, rv = []);
    return rv;
  }
  function getChildNodesSnapshot(node) {
    var result = [], i = 0;
    for (var child = node.firstChild; child; child = child.nextSibling) {
      result[i++] = child;
    }
    return result;
  }
  var request = oneOf(window, [ "requestAnimationFrame", "mozRequestAnimationFrame", "webkitRequestAnimationFrame", "setTimeout" ]);
  var pendingDirtyRenderers = [];
  var renderTimer;
  function renderAllPending() {
    for (var i = 0; i < pendingDirtyRenderers.length; i++) {
      var renderer = pendingDirtyRenderers[i];
      var parentRenderer = renderer.parentRenderer;
      if (parentRenderer && parentRenderer.dirty) continue;
      renderer.render();
    }
    pendingDirtyRenderers = [];
  }
  function handleRequestAnimationFrame() {
    renderTimer = null;
    renderAllPending();
  }
  function getRendererForHost(host) {
    var renderer = rendererForHostTable.get(host);
    if (!renderer) {
      renderer = new ShadowRenderer(host);
      rendererForHostTable.set(host, renderer);
    }
    return renderer;
  }
  function getShadowRootAncestor(node) {
    var root = getTreeScope(node).root;
    if (root instanceof ShadowRoot) return root;
    return null;
  }
  function getRendererForShadowRoot(shadowRoot) {
    return getRendererForHost(shadowRoot.host);
  }
  var spliceDiff = new ArraySplice();
  spliceDiff.equals = function(renderNode, rawNode) {
    return unwrap(renderNode.node) === rawNode;
  };
  function RenderNode(node) {
    this.skip = false;
    this.node = node;
    this.childNodes = [];
  }
  RenderNode.prototype = {
    append: function(node) {
      var rv = new RenderNode(node);
      this.childNodes.push(rv);
      return rv;
    },
    sync: function(opt_added) {
      if (this.skip) return;
      var nodeWrapper = this.node;
      var newChildren = this.childNodes;
      var oldChildren = getChildNodesSnapshot(unwrap(nodeWrapper));
      var added = opt_added || new WeakMap();
      var splices = spliceDiff.calculateSplices(newChildren, oldChildren);
      var newIndex = 0, oldIndex = 0;
      var lastIndex = 0;
      for (var i = 0; i < splices.length; i++) {
        var splice = splices[i];
        for (;lastIndex < splice.index; lastIndex++) {
          oldIndex++;
          newChildren[newIndex++].sync(added);
        }
        var removedCount = splice.removed.length;
        for (var j = 0; j < removedCount; j++) {
          var wrapper = wrap(oldChildren[oldIndex++]);
          if (!added.get(wrapper)) remove(wrapper);
        }
        var addedCount = splice.addedCount;
        var refNode = oldChildren[oldIndex] && wrap(oldChildren[oldIndex]);
        for (var j = 0; j < addedCount; j++) {
          var newChildRenderNode = newChildren[newIndex++];
          var newChildWrapper = newChildRenderNode.node;
          insertBefore(nodeWrapper, newChildWrapper, refNode);
          added.set(newChildWrapper, true);
          newChildRenderNode.sync(added);
        }
        lastIndex += addedCount;
      }
      for (var i = lastIndex; i < newChildren.length; i++) {
        newChildren[i].sync(added);
      }
    }
  };
  function ShadowRenderer(host) {
    this.host = host;
    this.dirty = false;
    this.invalidateAttributes();
    this.associateNode(host);
  }
  ShadowRenderer.prototype = {
    render: function(opt_renderNode) {
      if (!this.dirty) return;
      this.invalidateAttributes();
      var host = this.host;
      this.distribution(host);
      var renderNode = opt_renderNode || new RenderNode(host);
      this.buildRenderTree(renderNode, host);
      var topMostRenderer = !opt_renderNode;
      if (topMostRenderer) renderNode.sync();
      this.dirty = false;
    },
    get parentRenderer() {
      return getTreeScope(this.host).renderer;
    },
    invalidate: function() {
      if (!this.dirty) {
        this.dirty = true;
        var parentRenderer = this.parentRenderer;
        if (parentRenderer) parentRenderer.invalidate();
        pendingDirtyRenderers.push(this);
        if (renderTimer) return;
        renderTimer = window[request](handleRequestAnimationFrame, 0);
      }
    },
    distribution: function(root) {
      this.resetAllSubtrees(root);
      this.distributionResolution(root);
    },
    resetAll: function(node) {
      if (isInsertionPoint(node)) resetDistributedNodes(node); else resetDestinationInsertionPoints(node);
      this.resetAllSubtrees(node);
    },
    resetAllSubtrees: function(node) {
      for (var child = node.firstChild; child; child = child.nextSibling) {
        this.resetAll(child);
      }
      if (node.shadowRoot) this.resetAll(node.shadowRoot);
      if (node.olderShadowRoot) this.resetAll(node.olderShadowRoot);
    },
    distributionResolution: function(node) {
      if (isShadowHost(node)) {
        var shadowHost = node;
        var pool = poolPopulation(shadowHost);
        var shadowTrees = getShadowTrees(shadowHost);
        for (var i = 0; i < shadowTrees.length; i++) {
          this.poolDistribution(shadowTrees[i], pool);
        }
        for (var i = shadowTrees.length - 1; i >= 0; i--) {
          var shadowTree = shadowTrees[i];
          var shadow = getShadowInsertionPoint(shadowTree);
          if (shadow) {
            var olderShadowRoot = shadowTree.olderShadowRoot;
            if (olderShadowRoot) {
              pool = poolPopulation(olderShadowRoot);
            }
            for (var j = 0; j < pool.length; j++) {
              destributeNodeInto(pool[j], shadow);
            }
          }
          this.distributionResolution(shadowTree);
        }
      }
      for (var child = node.firstChild; child; child = child.nextSibling) {
        this.distributionResolution(child);
      }
    },
    poolDistribution: function(node, pool) {
      if (node instanceof HTMLShadowElement) return;
      if (node instanceof HTMLContentElement) {
        var content = node;
        this.updateDependentAttributes(content.getAttribute("select"));
        var anyDistributed = false;
        for (var i = 0; i < pool.length; i++) {
          var node = pool[i];
          if (!node) continue;
          if (matches(node, content)) {
            destributeNodeInto(node, content);
            pool[i] = undefined;
            anyDistributed = true;
          }
        }
        if (!anyDistributed) {
          for (var child = content.firstChild; child; child = child.nextSibling) {
            destributeNodeInto(child, content);
          }
        }
        return;
      }
      for (var child = node.firstChild; child; child = child.nextSibling) {
        this.poolDistribution(child, pool);
      }
    },
    buildRenderTree: function(renderNode, node) {
      var children = this.compose(node);
      for (var i = 0; i < children.length; i++) {
        var child = children[i];
        var childRenderNode = renderNode.append(child);
        this.buildRenderTree(childRenderNode, child);
      }
      if (isShadowHost(node)) {
        var renderer = getRendererForHost(node);
        renderer.dirty = false;
      }
    },
    compose: function(node) {
      var children = [];
      var p = node.shadowRoot || node;
      for (var child = p.firstChild; child; child = child.nextSibling) {
        if (isInsertionPoint(child)) {
          this.associateNode(p);
          var distributedNodes = getDistributedNodes(child);
          for (var j = 0; j < distributedNodes.length; j++) {
            var distributedNode = distributedNodes[j];
            if (isFinalDestination(child, distributedNode)) children.push(distributedNode);
          }
        } else {
          children.push(child);
        }
      }
      return children;
    },
    invalidateAttributes: function() {
      this.attributes = Object.create(null);
    },
    updateDependentAttributes: function(selector) {
      if (!selector) return;
      var attributes = this.attributes;
      if (/\.\w+/.test(selector)) attributes["class"] = true;
      if (/#\w+/.test(selector)) attributes["id"] = true;
      selector.replace(/\[\s*([^\s=\|~\]]+)/g, function(_, name) {
        attributes[name] = true;
      });
    },
    dependsOnAttribute: function(name) {
      return this.attributes[name];
    },
    associateNode: function(node) {
      unsafeUnwrap(node).polymerShadowRenderer_ = this;
    }
  };
  function poolPopulation(node) {
    var pool = [];
    for (var child = node.firstChild; child; child = child.nextSibling) {
      if (isInsertionPoint(child)) {
        pool.push.apply(pool, getDistributedNodes(child));
      } else {
        pool.push(child);
      }
    }
    return pool;
  }
  function getShadowInsertionPoint(node) {
    if (node instanceof HTMLShadowElement) return node;
    if (node instanceof HTMLContentElement) return null;
    for (var child = node.firstChild; child; child = child.nextSibling) {
      var res = getShadowInsertionPoint(child);
      if (res) return res;
    }
    return null;
  }
  function destributeNodeInto(child, insertionPoint) {
    getDistributedNodes(insertionPoint).push(child);
    var points = destinationInsertionPointsTable.get(child);
    if (!points) destinationInsertionPointsTable.set(child, [ insertionPoint ]); else points.push(insertionPoint);
  }
  function getDestinationInsertionPoints(node) {
    return destinationInsertionPointsTable.get(node);
  }
  function resetDestinationInsertionPoints(node) {
    destinationInsertionPointsTable.set(node, undefined);
  }
  var selectorStartCharRe = /^(:not\()?[*.#[a-zA-Z_|]/;
  function matches(node, contentElement) {
    var select = contentElement.getAttribute("select");
    if (!select) return true;
    select = select.trim();
    if (!select) return true;
    if (!(node instanceof Element)) return false;
    if (!selectorStartCharRe.test(select)) return false;
    try {
      return node.matches(select);
    } catch (ex) {
      return false;
    }
  }
  function isFinalDestination(insertionPoint, node) {
    var points = getDestinationInsertionPoints(node);
    return points && points[points.length - 1] === insertionPoint;
  }
  function isInsertionPoint(node) {
    return node instanceof HTMLContentElement || node instanceof HTMLShadowElement;
  }
  function isShadowHost(shadowHost) {
    return shadowHost.shadowRoot;
  }
  function getShadowTrees(host) {
    var trees = [];
    for (var tree = host.shadowRoot; tree; tree = tree.olderShadowRoot) {
      trees.push(tree);
    }
    return trees;
  }
  function render(host) {
    new ShadowRenderer(host).render();
  }
  Node.prototype.invalidateShadowRenderer = function(force) {
    var renderer = unsafeUnwrap(this).polymerShadowRenderer_;
    if (renderer) {
      renderer.invalidate();
      return true;
    }
    return false;
  };
  HTMLContentElement.prototype.getDistributedNodes = HTMLShadowElement.prototype.getDistributedNodes = function() {
    renderAllPending();
    return getDistributedNodes(this);
  };
  Element.prototype.getDestinationInsertionPoints = function() {
    renderAllPending();
    return getDestinationInsertionPoints(this) || [];
  };
  HTMLContentElement.prototype.nodeIsInserted_ = HTMLShadowElement.prototype.nodeIsInserted_ = function() {
    this.invalidateShadowRenderer();
    var shadowRoot = getShadowRootAncestor(this);
    var renderer;
    if (shadowRoot) renderer = getRendererForShadowRoot(shadowRoot);
    unsafeUnwrap(this).polymerShadowRenderer_ = renderer;
    if (renderer) renderer.invalidate();
  };
  scope.getRendererForHost = getRendererForHost;
  scope.getShadowTrees = getShadowTrees;
  scope.renderAllPending = renderAllPending;
  scope.getDestinationInsertionPoints = getDestinationInsertionPoints;
  scope.visual = {
    insertBefore: insertBefore,
    remove: remove
  };
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var HTMLElement = scope.wrappers.HTMLElement;
  var assert = scope.assert;
  var mixin = scope.mixin;
  var registerWrapper = scope.registerWrapper;
  var unwrap = scope.unwrap;
  var wrap = scope.wrap;
  var elementsWithFormProperty = [ "HTMLButtonElement", "HTMLFieldSetElement", "HTMLInputElement", "HTMLKeygenElement", "HTMLLabelElement", "HTMLLegendElement", "HTMLObjectElement", "HTMLOutputElement", "HTMLTextAreaElement" ];
  function createWrapperConstructor(name) {
    if (!window[name]) return;
    assert(!scope.wrappers[name]);
    var GeneratedWrapper = function(node) {
      HTMLElement.call(this, node);
    };
    GeneratedWrapper.prototype = Object.create(HTMLElement.prototype);
    mixin(GeneratedWrapper.prototype, {
      get form() {
        return wrap(unwrap(this).form);
      }
    });
    registerWrapper(window[name], GeneratedWrapper, document.createElement(name.slice(4, -7)));
    scope.wrappers[name] = GeneratedWrapper;
  }
  elementsWithFormProperty.forEach(createWrapperConstructor);
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var registerWrapper = scope.registerWrapper;
  var setWrapper = scope.setWrapper;
  var unsafeUnwrap = scope.unsafeUnwrap;
  var unwrap = scope.unwrap;
  var unwrapIfNeeded = scope.unwrapIfNeeded;
  var wrap = scope.wrap;
  var OriginalSelection = window.Selection;
  function Selection(impl) {
    setWrapper(impl, this);
  }
  Selection.prototype = {
    get anchorNode() {
      return wrap(unsafeUnwrap(this).anchorNode);
    },
    get focusNode() {
      return wrap(unsafeUnwrap(this).focusNode);
    },
    addRange: function(range) {
      unsafeUnwrap(this).addRange(unwrap(range));
    },
    collapse: function(node, index) {
      unsafeUnwrap(this).collapse(unwrapIfNeeded(node), index);
    },
    containsNode: function(node, allowPartial) {
      return unsafeUnwrap(this).containsNode(unwrapIfNeeded(node), allowPartial);
    },
    extend: function(node, offset) {
      unsafeUnwrap(this).extend(unwrapIfNeeded(node), offset);
    },
    getRangeAt: function(index) {
      return wrap(unsafeUnwrap(this).getRangeAt(index));
    },
    removeRange: function(range) {
      unsafeUnwrap(this).removeRange(unwrap(range));
    },
    selectAllChildren: function(node) {
      unsafeUnwrap(this).selectAllChildren(unwrapIfNeeded(node));
    },
    toString: function() {
      return unsafeUnwrap(this).toString();
    }
  };
  registerWrapper(window.Selection, Selection, window.getSelection());
  scope.wrappers.Selection = Selection;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var GetElementsByInterface = scope.GetElementsByInterface;
  var Node = scope.wrappers.Node;
  var ParentNodeInterface = scope.ParentNodeInterface;
  var Selection = scope.wrappers.Selection;
  var SelectorsInterface = scope.SelectorsInterface;
  var ShadowRoot = scope.wrappers.ShadowRoot;
  var TreeScope = scope.TreeScope;
  var cloneNode = scope.cloneNode;
  var defineWrapGetter = scope.defineWrapGetter;
  var elementFromPoint = scope.elementFromPoint;
  var forwardMethodsToWrapper = scope.forwardMethodsToWrapper;
  var matchesNames = scope.matchesNames;
  var mixin = scope.mixin;
  var registerWrapper = scope.registerWrapper;
  var renderAllPending = scope.renderAllPending;
  var rewrap = scope.rewrap;
  var setWrapper = scope.setWrapper;
  var unsafeUnwrap = scope.unsafeUnwrap;
  var unwrap = scope.unwrap;
  var wrap = scope.wrap;
  var wrapEventTargetMethods = scope.wrapEventTargetMethods;
  var wrapNodeList = scope.wrapNodeList;
  var implementationTable = new WeakMap();
  function Document(node) {
    Node.call(this, node);
    this.treeScope_ = new TreeScope(this, null);
  }
  Document.prototype = Object.create(Node.prototype);
  defineWrapGetter(Document, "documentElement");
  defineWrapGetter(Document, "body");
  defineWrapGetter(Document, "head");
  function wrapMethod(name) {
    var original = document[name];
    Document.prototype[name] = function() {
      return wrap(original.apply(unsafeUnwrap(this), arguments));
    };
  }
  [ "createComment", "createDocumentFragment", "createElement", "createElementNS", "createEvent", "createEventNS", "createRange", "createTextNode", "getElementById" ].forEach(wrapMethod);
  var originalAdoptNode = document.adoptNode;
  function adoptNodeNoRemove(node, doc) {
    originalAdoptNode.call(unsafeUnwrap(doc), unwrap(node));
    adoptSubtree(node, doc);
  }
  function adoptSubtree(node, doc) {
    if (node.shadowRoot) doc.adoptNode(node.shadowRoot);
    if (node instanceof ShadowRoot) adoptOlderShadowRoots(node, doc);
    for (var child = node.firstChild; child; child = child.nextSibling) {
      adoptSubtree(child, doc);
    }
  }
  function adoptOlderShadowRoots(shadowRoot, doc) {
    var oldShadowRoot = shadowRoot.olderShadowRoot;
    if (oldShadowRoot) doc.adoptNode(oldShadowRoot);
  }
  var originalGetSelection = document.getSelection;
  mixin(Document.prototype, {
    adoptNode: function(node) {
      if (node.parentNode) node.parentNode.removeChild(node);
      adoptNodeNoRemove(node, this);
      return node;
    },
    elementFromPoint: function(x, y) {
      return elementFromPoint(this, this, x, y);
    },
    importNode: function(node, deep) {
      return cloneNode(node, deep, unsafeUnwrap(this));
    },
    getSelection: function() {
      renderAllPending();
      return new Selection(originalGetSelection.call(unwrap(this)));
    },
    getElementsByName: function(name) {
      return SelectorsInterface.querySelectorAll.call(this, "[name=" + JSON.stringify(String(name)) + "]");
    }
  });
  if (document.registerElement) {
    var originalRegisterElement = document.registerElement;
    Document.prototype.registerElement = function(tagName, object) {
      var prototype, extendsOption;
      if (object !== undefined) {
        prototype = object.prototype;
        extendsOption = object.extends;
      }
      if (!prototype) prototype = Object.create(HTMLElement.prototype);
      if (scope.nativePrototypeTable.get(prototype)) {
        throw new Error("NotSupportedError");
      }
      var proto = Object.getPrototypeOf(prototype);
      var nativePrototype;
      var prototypes = [];
      while (proto) {
        nativePrototype = scope.nativePrototypeTable.get(proto);
        if (nativePrototype) break;
        prototypes.push(proto);
        proto = Object.getPrototypeOf(proto);
      }
      if (!nativePrototype) {
        throw new Error("NotSupportedError");
      }
      var newPrototype = Object.create(nativePrototype);
      for (var i = prototypes.length - 1; i >= 0; i--) {
        newPrototype = Object.create(newPrototype);
      }
      [ "createdCallback", "attachedCallback", "detachedCallback", "attributeChangedCallback" ].forEach(function(name) {
        var f = prototype[name];
        if (!f) return;
        newPrototype[name] = function() {
          if (!(wrap(this) instanceof CustomElementConstructor)) {
            rewrap(this);
          }
          f.apply(wrap(this), arguments);
        };
      });
      var p = {
        prototype: newPrototype
      };
      if (extendsOption) p.extends = extendsOption;
      function CustomElementConstructor(node) {
        if (!node) {
          if (extendsOption) {
            return document.createElement(extendsOption, tagName);
          } else {
            return document.createElement(tagName);
          }
        }
        setWrapper(node, this);
      }
      CustomElementConstructor.prototype = prototype;
      CustomElementConstructor.prototype.constructor = CustomElementConstructor;
      scope.constructorTable.set(newPrototype, CustomElementConstructor);
      scope.nativePrototypeTable.set(prototype, newPrototype);
      var nativeConstructor = originalRegisterElement.call(unwrap(this), tagName, p);
      return CustomElementConstructor;
    };
    forwardMethodsToWrapper([ window.HTMLDocument || window.Document ], [ "registerElement" ]);
  }
  forwardMethodsToWrapper([ window.HTMLBodyElement, window.HTMLDocument || window.Document, window.HTMLHeadElement, window.HTMLHtmlElement ], [ "appendChild", "compareDocumentPosition", "contains", "getElementsByClassName", "getElementsByTagName", "getElementsByTagNameNS", "insertBefore", "querySelector", "querySelectorAll", "removeChild", "replaceChild" ]);
  forwardMethodsToWrapper([ window.HTMLBodyElement, window.HTMLHeadElement, window.HTMLHtmlElement ], matchesNames);
  forwardMethodsToWrapper([ window.HTMLDocument || window.Document ], [ "adoptNode", "importNode", "contains", "createComment", "createDocumentFragment", "createElement", "createElementNS", "createEvent", "createEventNS", "createRange", "createTextNode", "elementFromPoint", "getElementById", "getElementsByName", "getSelection" ]);
  mixin(Document.prototype, GetElementsByInterface);
  mixin(Document.prototype, ParentNodeInterface);
  mixin(Document.prototype, SelectorsInterface);
  mixin(Document.prototype, {
    get implementation() {
      var implementation = implementationTable.get(this);
      if (implementation) return implementation;
      implementation = new DOMImplementation(unwrap(this).implementation);
      implementationTable.set(this, implementation);
      return implementation;
    },
    get defaultView() {
      return wrap(unwrap(this).defaultView);
    }
  });
  registerWrapper(window.Document, Document, document.implementation.createHTMLDocument(""));
  if (window.HTMLDocument) registerWrapper(window.HTMLDocument, Document);
  wrapEventTargetMethods([ window.HTMLBodyElement, window.HTMLDocument || window.Document, window.HTMLHeadElement ]);
  function DOMImplementation(impl) {
    setWrapper(impl, this);
  }
  function wrapImplMethod(constructor, name) {
    var original = document.implementation[name];
    constructor.prototype[name] = function() {
      return wrap(original.apply(unsafeUnwrap(this), arguments));
    };
  }
  function forwardImplMethod(constructor, name) {
    var original = document.implementation[name];
    constructor.prototype[name] = function() {
      return original.apply(unsafeUnwrap(this), arguments);
    };
  }
  wrapImplMethod(DOMImplementation, "createDocumentType");
  wrapImplMethod(DOMImplementation, "createDocument");
  wrapImplMethod(DOMImplementation, "createHTMLDocument");
  forwardImplMethod(DOMImplementation, "hasFeature");
  registerWrapper(window.DOMImplementation, DOMImplementation);
  forwardMethodsToWrapper([ window.DOMImplementation ], [ "createDocumentType", "createDocument", "createHTMLDocument", "hasFeature" ]);
  scope.adoptNodeNoRemove = adoptNodeNoRemove;
  scope.wrappers.DOMImplementation = DOMImplementation;
  scope.wrappers.Document = Document;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var EventTarget = scope.wrappers.EventTarget;
  var Selection = scope.wrappers.Selection;
  var mixin = scope.mixin;
  var registerWrapper = scope.registerWrapper;
  var renderAllPending = scope.renderAllPending;
  var unwrap = scope.unwrap;
  var unwrapIfNeeded = scope.unwrapIfNeeded;
  var wrap = scope.wrap;
  var OriginalWindow = window.Window;
  var originalGetComputedStyle = window.getComputedStyle;
  var originalGetDefaultComputedStyle = window.getDefaultComputedStyle;
  var originalGetSelection = window.getSelection;
  function Window(impl) {
    EventTarget.call(this, impl);
  }
  Window.prototype = Object.create(EventTarget.prototype);
  OriginalWindow.prototype.getComputedStyle = function(el, pseudo) {
    return wrap(this || window).getComputedStyle(unwrapIfNeeded(el), pseudo);
  };
  if (originalGetDefaultComputedStyle) {
    OriginalWindow.prototype.getDefaultComputedStyle = function(el, pseudo) {
      return wrap(this || window).getDefaultComputedStyle(unwrapIfNeeded(el), pseudo);
    };
  }
  OriginalWindow.prototype.getSelection = function() {
    return wrap(this || window).getSelection();
  };
  delete window.getComputedStyle;
  delete window.getDefaultComputedStyle;
  delete window.getSelection;
  [ "addEventListener", "removeEventListener", "dispatchEvent" ].forEach(function(name) {
    OriginalWindow.prototype[name] = function() {
      var w = wrap(this || window);
      return w[name].apply(w, arguments);
    };
    delete window[name];
  });
  mixin(Window.prototype, {
    getComputedStyle: function(el, pseudo) {
      renderAllPending();
      return originalGetComputedStyle.call(unwrap(this), unwrapIfNeeded(el), pseudo);
    },
    getSelection: function() {
      renderAllPending();
      return new Selection(originalGetSelection.call(unwrap(this)));
    },
    get document() {
      return wrap(unwrap(this).document);
    }
  });
  if (originalGetDefaultComputedStyle) {
    Window.prototype.getDefaultComputedStyle = function(el, pseudo) {
      renderAllPending();
      return originalGetDefaultComputedStyle.call(unwrap(this), unwrapIfNeeded(el), pseudo);
    };
  }
  registerWrapper(OriginalWindow, Window, window);
  scope.wrappers.Window = Window;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var unwrap = scope.unwrap;
  var OriginalDataTransfer = window.DataTransfer || window.Clipboard;
  var OriginalDataTransferSetDragImage = OriginalDataTransfer.prototype.setDragImage;
  if (OriginalDataTransferSetDragImage) {
    OriginalDataTransfer.prototype.setDragImage = function(image, x, y) {
      OriginalDataTransferSetDragImage.call(this, unwrap(image), x, y);
    };
  }
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var registerWrapper = scope.registerWrapper;
  var setWrapper = scope.setWrapper;
  var unwrap = scope.unwrap;
  var OriginalFormData = window.FormData;
  if (!OriginalFormData) return;
  function FormData(formElement) {
    var impl;
    if (formElement instanceof OriginalFormData) {
      impl = formElement;
    } else {
      impl = new OriginalFormData(formElement && unwrap(formElement));
    }
    setWrapper(impl, this);
  }
  registerWrapper(OriginalFormData, FormData, new OriginalFormData());
  scope.wrappers.FormData = FormData;
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var unwrapIfNeeded = scope.unwrapIfNeeded;
  var originalSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.send = function(obj) {
    return originalSend.call(this, unwrapIfNeeded(obj));
  };
})(window.ShadowDOMPolyfill);

(function(scope) {
  "use strict";
  var isWrapperFor = scope.isWrapperFor;
  var elements = {
    a: "HTMLAnchorElement",
    area: "HTMLAreaElement",
    audio: "HTMLAudioElement",
    base: "HTMLBaseElement",
    body: "HTMLBodyElement",
    br: "HTMLBRElement",
    button: "HTMLButtonElement",
    canvas: "HTMLCanvasElement",
    caption: "HTMLTableCaptionElement",
    col: "HTMLTableColElement",
    content: "HTMLContentElement",
    data: "HTMLDataElement",
    datalist: "HTMLDataListElement",
    del: "HTMLModElement",
    dir: "HTMLDirectoryElement",
    div: "HTMLDivElement",
    dl: "HTMLDListElement",
    embed: "HTMLEmbedElement",
    fieldset: "HTMLFieldSetElement",
    font: "HTMLFontElement",
    form: "HTMLFormElement",
    frame: "HTMLFrameElement",
    frameset: "HTMLFrameSetElement",
    h1: "HTMLHeadingElement",
    head: "HTMLHeadElement",
    hr: "HTMLHRElement",
    html: "HTMLHtmlElement",
    iframe: "HTMLIFrameElement",
    img: "HTMLImageElement",
    input: "HTMLInputElement",
    keygen: "HTMLKeygenElement",
    label: "HTMLLabelElement",
    legend: "HTMLLegendElement",
    li: "HTMLLIElement",
    link: "HTMLLinkElement",
    map: "HTMLMapElement",
    marquee: "HTMLMarqueeElement",
    menu: "HTMLMenuElement",
    menuitem: "HTMLMenuItemElement",
    meta: "HTMLMetaElement",
    meter: "HTMLMeterElement",
    object: "HTMLObjectElement",
    ol: "HTMLOListElement",
    optgroup: "HTMLOptGroupElement",
    option: "HTMLOptionElement",
    output: "HTMLOutputElement",
    p: "HTMLParagraphElement",
    param: "HTMLParamElement",
    pre: "HTMLPreElement",
    progress: "HTMLProgressElement",
    q: "HTMLQuoteElement",
    script: "HTMLScriptElement",
    select: "HTMLSelectElement",
    shadow: "HTMLShadowElement",
    source: "HTMLSourceElement",
    span: "HTMLSpanElement",
    style: "HTMLStyleElement",
    table: "HTMLTableElement",
    tbody: "HTMLTableSectionElement",
    template: "HTMLTemplateElement",
    textarea: "HTMLTextAreaElement",
    thead: "HTMLTableSectionElement",
    time: "HTMLTimeElement",
    title: "HTMLTitleElement",
    tr: "HTMLTableRowElement",
    track: "HTMLTrackElement",
    ul: "HTMLUListElement",
    video: "HTMLVideoElement"
  };
  function overrideConstructor(tagName) {
    var nativeConstructorName = elements[tagName];
    var nativeConstructor = window[nativeConstructorName];
    if (!nativeConstructor) return;
    var element = document.createElement(tagName);
    var wrapperConstructor = element.constructor;
    window[nativeConstructorName] = wrapperConstructor;
  }
  Object.keys(elements).forEach(overrideConstructor);
  Object.getOwnPropertyNames(scope.wrappers).forEach(function(name) {
    window[name] = scope.wrappers[name];
  });
})(window.ShadowDOMPolyfill);