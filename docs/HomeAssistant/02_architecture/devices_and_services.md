---
title: "Entities: integrating devices & services"
sidebar_label: "Introduction"
---

Integrations can represent devices & services in Home Assistant. The data points are represented as entities. Entities are standardized by other integrations like `light`, `switch`, etc. Standardized entities come with actions for control, but an integration can also provide their own service actions in case something is not standardized.

An entity abstracts away the internal workings of Home Assistant. As an integrator, you don't have to worry about how service actions or the state machine work. Instead, you extend an entity class and implement the necessary properties and methods for the device type that you're integrating.

<img className='invertDark'
  src='/img/en/architecture/integrating-devices-services.svg'
  alt='Integrating devices & services' />

<!--
  https://docs.google.com/drawings/d/1oysZ1VMcPPuyKhY4tequsBWcblDdLydbWxlu6bH6678/edit?usp=sharing
-->

Configuration is provided by the user via a [Config Entry](../config_entries_index.md) or in special/legacy cases via [configuration.yaml](../configuration_yaml_index.md).

The device integration (i.e. `hue`) will use this configuration to set up a connection with the device/service. It will forward the config entry (legacy uses discovery helper) to set up its entities in their respective integrations (light, switch). The device integration can also register their own service actions for things that are not made standardized. These actions are published under the integration's domain, ie `hue.activate_scene`.

The entity integration (i.e. `light`) is responsible for defining the abstract entity class and services to control the entities.

The Entity Component helper is responsible for distributing the configuration to the platforms, forward discovery and collect entities for service calls.

The Entity Platform helper manages all entities for the platform and polls them for updates if necessary. When adding entities, the Entity Platform is responsible for registering the entity with the device and entity registries.

Integration Platform (i.e. `hue.light`) uses configuration to query the external device/service and create entities to be added. It is also possible for integration platforms to register entity services. These services will work on all entities of the device integration for the entity integration (i.e. all Hue light entities). These services are published under the device integration domain.

## Entity interaction with Home Assistant Core

The integration entity class that inherits from the entity base class is responsible for fetching the data and handle the service calls. If polling is disabled, it is also responsible for telling Home Assistant when data is available.

<img className='invertDark'
  src='/img/en/architecture/entity-core-interaction.svg'
  alt='Entities interacting with core' />

<!--
  https://docs.google.com/drawings/d/12Z0t6hriYrQZ2L5Ou7BVhPDd9iGvOvFiGniX5sgqsE4/edit?usp=sharing
-->

The entity base class (defined by the entity integration)  is responsible for formatting the data and writing it to the state machine.

The entity registry will write an `unavailable` state for any registered entity that is not currently backed by an entity object.

## Entity data hierarchy

<img className='invertDark'
  style={{maxWidth: "200px"}}
  src='/img/en/architecture/entity-data-hierarchy.svg'
  alt='Entity hierarchy' />

<!--
  https://docs.google.com/drawings/d/1TorZABszaj3m7tgTyf-EMrheYCj3HAvwXB8YmJW5NZ4/edit?usp=sharing
-->

Delete, disable or re-enable any object and all objects below will be adjusted accordingly.
