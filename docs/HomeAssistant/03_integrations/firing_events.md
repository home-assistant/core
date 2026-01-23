---
title: "Firing events"
---

:::info 
Rather than emitting events directly on the event bus, integrations are generally encouraged to publish them as [event entities](/docs/core/entity/event.md) instead. This approach enhances the user experience by making it easier for the user to browse and identify all available events. 
:::

Some integrations represent devices or services that have events, like when motion is detected or a momentary button is pushed. An integration can make these available to users by firing them as events in Home Assistant.

Your integration should fire events of type `<domain>_event`. For example, the ZHA integration fires `zha_event` events.

If the event is related to a specific device/service, it should be correctly attributed. Do this by adding a `device_id` attribute to the event data that contains the device identifier from the device registry.

```
event_data = {
    "device_id": "my-device-id",
    "type": "motion_detected",
}
hass.bus.async_fire("mydomain_event", event_data)
```

If a device or service only fires events, you need to [manually register it in the device registry](device_registry_index.md#manual-registration).

## Making events accessible to users

A [Device trigger](device_automation_trigger.md) can be attached to a specific event based on the payload, and will make the event accessible to users. With a device trigger a user will be able to see all available events for the device and use it in their automations.

## What not to do

Event related code should not be part of the entity logic of your integration. You want to enable the logic of converting your integration events to Home Assistant events from inside `async_setup_entry` inside `__init__.py`.

Entity state should not represent events. For example, you don't want to have a binary sensor that is `on` for 30 seconds when an event happens.
