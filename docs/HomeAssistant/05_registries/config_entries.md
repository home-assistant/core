---
title: Config entries
---

Config entries are configuration data that are persistently stored by Home Assistant. A config entry is created by a user via the UI. The UI flow is powered by a [config flow handler](config_entries_config_flow_handler.md) as defined by the integration.

Once created, config entries can be removed by the user. Optionally, config entries can be changed by the user via a [reconfigure step](config_entries_config_flow_handler.md#reconfigure) or [options flow handler](config_entries_options_flow_handler.md), also defined by the integration.

### Config subentries

Config entries can logically separate the stored configuration data into subentries, which can be added by the user via the UI to an existing config entry. An example of this is an integration providing weather forecasts, where the config entry stores authentication details and each location for which weather forecasts should be provided is stored as a subentry.

Similar to config entries, subentries can optionally support a reconfigure step.

## Lifecycle

| State | Description |
| ----- | ----------- |
| not loaded | The config entry has not been loaded. This is the initial state when a config entry is created or when Home Assistant is restarted. |
| setup in progress | An intermediate state while attempting to load the config entry. |
| loaded | The config entry has been loaded. |
| setup error | An error occurred when trying to set up the config entry. |
| setup retry | A dependency of the config entry was not ready yet. Home Assistant will automatically retry loading this config entry in the future. Time between attempts will automatically increase. |
| migration error | The config entry had to be migrated to a newer version, but the migration failed. |
| unload in progress | An intermediate state while attempting to unload the config entry. |
| failed unload | The config entry was attempted to be unloaded, but this was either not supported or it raised an exception. |

More information about surfacing errors and requesting a retry are in [Handling Setup Failures](integration_setup_failures.md#integrations-using-async_setup_entry).


## Setting up an entry

During startup, Home Assistant first calls the [normal integration setup](/creating_component_index.md),
and then calls the method `async_setup_entry(hass, entry)` for each entry. If a new Config Entry is
created at runtime, Home Assistant will also call `async_setup_entry(hass, entry)` ([example](https://github.com/home-assistant/core/blob/f18ddb628c3574bc82e21563d9ba901bd75bc8b5/homeassistant/components/hassio/__init__.py#L522)).

### For platforms

If an integration includes platforms, it will need to forward the Config Entry set up to the platform. This can
be done by calling the forward function on the config entry manager ([example](https://github.com/home-assistant/core/blob/f18ddb628c3574bc82e21563d9ba901bd75bc8b5/homeassistant/components/hassio/__init__.py#L529)):

```python
await hass.config_entries.async_forward_entry_setups(config_entry, ["light", "sensor", "switch"])
```

For a platform to support config entries, it will need to add a setup entry function ([example](https://github.com/home-assistant/core/blob/f18ddb628c3574bc82e21563d9ba901bd75bc8b5/homeassistant/components/hassio/__init__.py#L522)):

```python
async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up entry."""
```

## Unloading entries

Integrations can optionally support unloading a config entry. When unloading an entry, the integration needs to clean up all entities, unsubscribe any event listener and close all connections. To implement this, add `async_unload_entry(hass, entry)` to your integration ([example](https://github.com/home-assistant/core/blob/f18ddb628c3574bc82e21563d9ba901bd75bc8b5/homeassistant/components/hassio/__init__.py#L534)). The state of the config entry is set to `ConfigEntryState.UNLOAD_IN_PROGRESS` before `async_unload_entry` is called.

For each platform that you forwarded the config entry to, you will need to forward the unloading too.

```python
async def async_unload_entry(hass: HomeAssistant, entry: MyConfigEntry) -> bool:
    """Unload a config entry."""
```

If you need to clean up resources used by an entity in a platform, have the entity implement the [`async_will_remove_from_hass`](core/entity.md#async_will_remove_from_hass) method.

## Removal of entries

If an integration needs to clean up code when an entry is removed, it can define a removal function `async_remove_entry`. The config entry is deleted from `hass.config_entries` before `async_remove_entry` is called.

```python
async def async_remove_entry(hass, entry) -> None:
    """Handle removal of an entry."""
```

## Migrating config entries to a new version

If the config entry version is changed, `async_migrate_entry` must be implemented to support the migration of old entries. This is documented in detail in the [config flow documentation](/config_entries_config_flow_handler.md#config-entry-migration)

```python
async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
```

## Modifying a config entry

A `ConfigEntry` object, including the data and options, must never be mutated directly by integrations, instead integrations must call `async_update_entry`, the use of which is illustrated in the [config flow documentation](/config_entries_config_flow_handler.md#config-entry-migration).

## Subscribing to config entry state changes

If you want to be notified about a `ConfigEntry` changing its `state` (e.g. from `ConfigEntryState.LOADED` to `ConfigEntryState.UNLOAD_IN_PROGRESS`), you can add a listener which will be notified to `async_on_state_change`. This helper also returns a callback you can call to remove the listener again. Subscribing to changes until the entry is unloaded would therefore be `entry.async_on_unload(entry.async_on_state_change(notify_me))`.
