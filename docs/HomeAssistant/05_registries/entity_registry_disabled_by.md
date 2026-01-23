---
title: Entity registry and disabling entities
sidebar_label: Disabling entities
---

The entity registry tracks all entities with unique IDs. For each entity, the registry keeps track of options that impact how the entity interacts with the core. One of these options is `disabled_by`.

When `disabled_by` is set and not `None`, the entity will not be added to Home Assistant when the integration passes it to `async_add_entities`.

## Integration architecture

Integrations will need to make sure that they work correctly when their entities get disabled. If your integration is keeping references to the created entity objects, it should register those references only inside the entity's lifecycle method `async_added_to_hass`. This lifecycle method is only called if the entity is actually added to Home Assistant (and so it's not disabled).

Entity disabling works with entities provided via a config entry or via an entry in configuration.yaml. If your integration is set up via a config entry and supports [unloading](config_entries_index.md#unloading-entries), Home Assistant will be able to reload your integration after entities have been enabled/disabled to apply the changes without a restart.

## Users editing the entity registry

One way an entity can be disabled is by the user editing the entity registry via the UI. In this case, the `disabled_by` value will be set to `RegistryEntryDisabler.USER`. This will only work with entities that are already registered.

## Integrations setting default value of disabled_by for new entity registry entries

As an integration you can control if your entity is enabled when it is first registered. This is controlled by the `entity_registry_enabled_default` property. It defaults to `True`, which means the entity will be enabled.

If the property returns `False`, the `disabled_by` value of the newly registered entity will be set to `RegistryEntryDisabler.INTEGRATION`.

## Config entry system options setting default value of disabled_by for new entity registry entries

The user can also control how new entities that are related to a config entry are received by setting the system option `disable_new_entities` of a config entry to `True`. This can be done via the UI.

If an entity is getting registered and this system option is set to `True`, the `disabled_by` property will be initialized as `RegistryEntryDisabler.CONFIG_ENTRY`.

If `disable_new_entities` is set to `True` and `entity_registry_enabled_default` returns `False`, the `disabled_by` value will be set to `RegistryEntryDisabler.INTEGRATION`.

## Integrations offering options to control disabled_by

Some integrations will want to offer options to the user to control which entities are being added to Home Assistant. For example, the Unifi integration offers options to enable/disable wireless and wired clients.

Integrations can offer options to users either via [configuration.yaml](/configuration_yaml_index.md) or using an [Options Flow](/config_entries_options_flow_handler.md).

If this option is offered by integrations, you should not leverage the disabled_by property in the entity registry. Instead, if entities are disabled via a config options flow, remove them from the device and entity registry.
