---
title: "Listening for events"
---

Your integration may need to take action when a specific event happens inside Home Assistant. Home Assistant provides event helpers to listen for particular event types and direct access to the event bus. The helpers are highly optimized to minimize the number of callbacks. If there is already a helper for the specific event you need to listen for, it is preferable to use the helper over listening to the event bus directly.

## Available event helpers

Event helpers are available in the `homeassistant.helpers.event` namespace. These functions return a callable that cancels the listener.

Sync versions of the below functions are also available without the `async_` prefix.

### Example

```python3
unsub = async_track_state_change_event(hass, entity_ids, state_automation_listener)
unsub()
```

### Tracking entity state changes

| Function                             | Use case
| ------------------------------------ | --------------------------------------------------------------------------
| `async_track_state_change`           | Track specific state changes
| `async_track_state_change_event`     | Track specific state change events indexed by entity_id
| `async_track_state_added_domain`     | Track state change events when an entity is added to domains
| `async_track_state_removed_domain`   | Track state change events when an entity is removed from domains
| `async_track_state_change_filtered`  | Track state changes with a TrackStates filter that can be updated
| `async_track_same_state`             | Track the state of entities for a period and run an action

### Tracking template changes

| Function                             | Use case
| ------------------------------------ | --------------------------------------------------------------------------
| `async_track_template`               | Add a listener that fires when a template evaluates to 'true'
| `async_track_template_result`        | Add a listener that fires when the result of a template changes

### Tracking entity registry changes

| Function                                    | Use case
| ------------------------------------------- | --------------------------------------------------------------------------
| `async_track_entity_registry_updated_event` | Track specific entity registry updated events indexed by entity_id

### Tracking time changes

| Function                                    | Use case
| ------------------------------------------- | --------------------------------------------------------------------------
| `async_track_point_in_time`                 | Add a listener that fires once after a specific point in time
| `async_track_point_in_utc_time`             | Add a listener that fires once after a specific point in UTC time
| `async_call_later`                          | Add a listener that is called with a delay
| `async_track_time_interval`                 | Add a listener that fires repetitively at every timedelta interval
| `async_track_utc_time_change`               | Add a listener that will fire if time matches a pattern
| `async_track_time_change`                   | Add a listener that will fire if local time matches a pattern

### Tracking the sun

| Function                                    | Use case
| ------------------------------------------- | --------------------------------------------------------------------------
| `async_track_sunrise`                       | Add a listener that will fire a specified offset from sunrise daily
| `async_track_sunset`                        | Add a listener that will fire a specified offset from sunset daily

## Listening to the event bus directly

There are two functions available to create listeners. Both functions return a callable that cancels the listener. 

- `async_listen_once` - Listen once for the event and never fire again
- `async_listen` - Listen until canceled

It's a rare case that `async_listen` is used since `EVENT_HOMEASSISTANT_START`, `EVENT_HOMEASSISTANT_STARTED`, and `EVENT_HOMEASSISTANT_STOP` are only ever fired once per run.

### Async context

```python3
cancel = hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, disconnect_service)
cancel()
```

```python3
cancel = hass.bus.async_listen(EVENT_STATE_CHANGED, forward_event)
cancel()
```

### Sync context
```python3
cancel = hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, disconnect_service)
cancel()
```

```python3
cancel = hass.bus.listen(EVENT_STATE_CHANGED, forward_event)
cancel()
```

### Common events

The below events are commonly listened to directly.

| Event Name                        | Description
| --------------------------------- | --------------------------------------------------------------------------
| `EVENT_HOMEASSISTANT_START`       | Completed the setup and entered the start phase
| `EVENT_HOMEASSISTANT_STARTED`     | Completed the start phase, and all integrations have had a chance to load; Mostly used by voice assistants and integrations that export states to external services
| `EVENT_HOMEASSISTANT_STOP`        | Entered the stop phase

### Other events

These events are rarely listened to directly unless the integration is part of the core. Often there is a helper available that consumes these events, and in that case, they should not be listened for directly.

| Event Name                        | Description                                  | Preferred helper
| --------------------------------- | -------------------------------------------- | ----------------------------
| `EVENT_HOMEASSISTANT_FINAL_WRITE` | The last opportunity to write data to disk   | 
| `EVENT_HOMEASSISTANT_CLOSE`       | Teardown                                     | 
| `EVENT_COMPONENT_LOADED`          | An integration has completed loading         | `homeassistant.helpers.start.async_at_start`
| `EVENT_SERVICE_REGISTERED`        | A new service has been registered            |
| `EVENT_SERVICE_REMOVED`           | A service has been removed                   |
| `EVENT_CALL_SERVICE`              | A service has been called                    |
| `EVENT_STATE_CHANGED`             | The state of an entity has changed           | [Tracking entity state changes](#tracking-entity-state-changes)
| `EVENT_THEMES_UPDATED`            | Themes have been updated                     |
| `EVENT_CORE_CONFIG_UPDATE`        | Core configuration has been updated          |
| `EVENT_ENTITY_REGISTRY_UPDATED`   | The entity registry has been updated         | [Tracking entity registry changes](#tracking-entity-registry-changes)
