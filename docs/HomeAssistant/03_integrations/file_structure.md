---
title: "Integration file structure"
sidebar_label: "File structure"
---

Each integration is stored inside a directory named after the integration domain. The domain is a short name consisting of characters and underscores. This domain has to be unique and cannot be changed. Example of the domain for the mobile app integration: `mobile_app`. So all files for this integration are in the folder `mobile_app/`.

The bare minimum content of this folder looks like this:

- `manifest.json`: The manifest file describes the integration and its dependencies. [More info](creating_integration_manifest.md)
- `__init__.py`: The component file. If the integration only offers a platform, you can keep this file limited to a docstring introducing the integration `"""The Mobile App integration."""`.

## Integrating devices - `light.py`, `switch.py` etc

If your integration is going to integrate one or more devices, you will need to do this by creating a platform that interacts with an entity integration. For example, if you want to represent a light device inside Home Assistant, you will create `light.py`, which will contain a light platform for the light integration.

- More info on [available entity integrations](core/entity.md).
- More info on [creating platforms](creating_platform_index.md).

## Integrating service actions - `services.yaml`

If your integration is going to register service actions, it will need to provide a description of the available actions. The description is stored in `services.yaml`. [More information about `services.yaml`.](dev_101_services.md)

## Data update coordinator - `coordinator.py`

There are multiple ways for your integration to receive data, including push or poll. Commonly integrations will fetch data with a single coordinated poll across all entities, which requires the use of a `DataUpdateCoordinator`.
If you want to use one, and you choose to create a subclass of it, it is recommended to define the coordinator class in `coordinator.py`. [More information about `DataUpdateCoordinator`](integration_fetching_data.md#coordinated-single-api-poll-for-data-for-all-entities).

## Where Home Assistant looks for integrations

Home Assistant will look for an integration when it sees the domain referenced in the config file (i.e. `mobile_app:`) or if it is a dependency of another integration. Home Assistant will look at the following locations:

- `<config directory>/custom_components/<domain>`
- `homeassistant/components/<domain>` (built-in integrations)

You can override a built-in integration by having an integration with the same domain in your `<config directory>/custom_components` folder. [The `manifest.json` file requires a version tag when you override a core integration](creating_integration_manifest/#version). An overridden core integration can be identified by a specific icon in the upper right corner of the integration box in the overview [![Open your Home Assistant instance and show your integrations.](https://my.home-assistant.io/badges/integrations.svg)](https://my.home-assistant.io/redirect/integrations/)
Note that overriding built-in integrations is not recommended as you will no longer get updates. It is recommended to pick a unique name.
