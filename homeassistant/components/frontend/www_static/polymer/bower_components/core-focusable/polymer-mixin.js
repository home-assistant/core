Polymer.mixin2 = function(prototype, mixin) {

  // adds a single mixin to prototype

  if (mixin.mixinPublish) {
    prototype.publish = prototype.publish || {};
    Polymer.mixin(prototype.publish, mixin.mixinPublish);
  }

  if (mixin.mixinDelegates) {
    prototype.eventDelegates = prototype.eventDelegates || {};
    for (var e in mixin.mixinDelegates) {
      if (!prototype.eventDelegates[e]) {
        prototype.eventDelegates[e] = mixin.mixinDelegates[e];
      }
    }
  }

  if (mixin.mixinObserve) {
    prototype.observe = prototype.observe || {};
    for (var o in mixin.mixinObserve) {
      if (!prototype.observe[o] && !prototype[o + 'Changed']) {
        prototype.observe[o] = mixin.mixinObserve[o];
      }
    }
  }

  Polymer.mixin(prototype, mixin);

  delete prototype.mixinPublish;
  delete prototype.mixinDelegates;
  delete prototype.mixinObserve;

  return prototype;
};