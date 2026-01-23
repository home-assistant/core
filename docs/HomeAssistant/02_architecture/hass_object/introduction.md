---
title: "Hass object"
sidebar_label: "Introduction"
---

While developing Home Assistant you will see a variable that is everywhere: `hass`. This is the Home Assistant instance that will give you access to all the various parts of the system.

### The `hass` object

The Home Assistant instance contains four objects to help you interact with the system.

| Object | Description |
| ------ | ----------- |
| `hass` | This is the instance of Home Assistant. Allows starting, stopping and enqueuing new jobs. |
| `hass.config` | This is the core configuration of Home Assistant exposing location, temperature preferences and config directory path. |
| `hass.states` | This is the StateMachine. It allows you to set states and track when they are changed. [See available methods.](https://developers.home-assistant.io/docs/dev_101_states) |
| `hass.bus` | This is the EventBus. It allows you to trigger and listen for events. [See available methods.](https://developers.home-assistant.io/docs/dev_101_events) |
| `hass.services` | This is the ServiceRegistry. It allows you to register service actions. [See available methods.](https://developers.home-assistant.io/docs/dev_101_services) |

<img class='invertDark'
  alt='Overview of the Home Assistant core architecture'
  src='/img/en/architecture/ha_architecture.svg'
/>

### Where to find `hass`

Depending on what you're writing, there are different ways the `hass` object is made available.

**Component**
Passed into `setup(hass, config)` or `async_setup(hass, config)`.

**Platform**
Passed into `setup_platform(hass, config, add_entities, discovery_info=None)` or `async_setup_platform(hass, config, async_add_entities, discovery_info=None)`.

**Entity**
Available as `self.hass` once the entity has been added via the `add_entities` callback inside a platform.
