<link rel="import" href="../bower_components/polymer/polymer.html">

<link rel="import" href="./partial-base.html">

<link rel="import" href="../components/ha-logbook.html">

<polymer-element name="entity-logbook" attributes="entity_id">
<template>

  <ha-logbook entries="{{entries}}"></ha-logbook>

</template>
<script>
  var storeListenerMixIn = window.hass.storeListenerMixIn;
  var logbookActions = window.hass.logbookActions;

  Polymer(Polymer.mixin({
    entries: null,

    attached: function() {
      this.listenToStores(true);
    },

    detached: function() {
      this.stopListeningToStores();
    },

    logbookStoreChanged: function(logbookStore) {
      if (logbookStore.isStale()) {
        logbookActions.fetch();
      }

      this.entries = logbookStore.all.toArray();
    },

    handleRefreshClick: function() {
      logbookActions.fetch();
    },
  }, storeListenerMixIn));
</script>
</polymer>
