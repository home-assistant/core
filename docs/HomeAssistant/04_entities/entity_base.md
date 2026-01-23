# Entity

For a generic introduction of entities, see [entities architecture](https://developers.home-assistant.io/docs/architecture/devices-and-services).

## Basic implementation

Below is an example switch entity that keeps track of its state in memory. In addition, the switch in the example represents the main feature of a device, meaning the entity has the same name as its device.

Please refer to [Entity naming](#entity-naming) for how to give an entity its own name.

```python
from homeassistant.components.switch import SwitchEntity


class MySwitch(SwitchEntity):
    _attr_has_entity_name = True

    def __init__(self):
        self._is_on = False
        self._attr_device_info = ...  # For automatic device registration
        self._attr_unique_id = ...

    @property
    def is_on(self):
        """If the switch is currently on or off."""
        return self._is_on

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._is_on = True

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self._is_on = False
```

That's all there is to it to build a switch entity! Continue reading to learn more or check out the [video tutorial](https://youtu.be/Cfasc9EgbMU?t=737).

## Updating the entity

An entity represents a device. There are various strategies to keep your entity in sync with the state of the device, the most popular one being polling.

### Polling

With polling, Home Assistant will ask the entity from time to time (depending on the update interval of the component) to fetch the latest state. Home Assistant will poll an entity when the `should_poll` property returns `True` (the default value). You can either implement your update logic using `update()` or the async method `async_update()`. This method should fetch the latest state from the device and store it in an instance variable for the properties to return it.

### Subscribing to updates

When you subscribe to updates, your code is responsible for letting Home Assistant know that an update is available. Make sure you have the `should_poll` property return `False`.

Whenever you receive a new state from your subscription, you can tell Home Assistant that an update is available by calling `schedule_update_ha_state()` or async callback `async_schedule_update_ha_state()`. Pass in the boolean `True` to the method if you want Home Assistant to call your update method before writing the update to Home Assistant.

## Generic properties

The entity base class has a few properties common among all Home Assistant entities. These properties can be added to any entity regardless of the type. All these properties are optional and don't need to be implemented.

These properties are always called when the state is written to the state machine.

> **TIP**
> Properties should always only return information from memory and not do I/O (like network requests). Implement `update()` or `async_update()` to fetch data.
> 
> Because these properties are always called when the state is written to the state machine, it is important to do as little work as possible in the property.
> 
> To avoid calculations in a property method, set the corresponding [entity class or instance attribute](#entity-class-or-instance-attributes), or if the values never change, use [entity descriptions](#entity-description).

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| assumed_state | bool | False | Return True if the state is based on our assumption instead of reading it from the device. |
| attribution | str | None | The branding text required by the API provider. |
| available | bool | True | Indicate if Home Assistant is able to read the state or control the underlying device. |
| device_class | str | None | Extra classification of what the device is. |
| entity_picture | str | None | Url of a picture to show for the entity. |
| extra_state_attributes | dict | None | Extra information to store in the state machine. |
| has_entity_name | bool | False | Return True if the entity's name property represents the entity itself. |
| name | str | None | Name of the entity. |
| should_poll | bool | True | Should Home Assistant check with the entity for an updated state. |
| state | str \| int \| float | None | The state of the entity. |
| supported_features | int | None | Flag features supported by the entity. |
| translation_key | str | None | A key for looking up translations. |

> **WARNING**
> It's allowed to change `device_class`, `supported_features` or any property included in a domain's `capability_attributes`. However, we recommend only changing them when absolutely required as it may cause resynchronization with voice assistants.

## Registry properties

The following properties are used to populate the entity and device registries. They only have an effect if `unique_id` is not None.

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| device_info | DeviceInfo | None | Device registry descriptor for automatic registration. |
| entity_category | EntityCategory | None | Classification (CONFIG, DIAGNOSTIC, etc.). |
| entity_registry_enabled_default | bool | True | Whether the entity is enabled by default. |
| entity_registry_visible_default | bool | True | Whether the entity is visible by default. |
| unique_id | str | None | A unique identifier (must be unique within a platform). |

## Entity naming

Avoid setting an entity's name to a hard coded English string; instead, the name should be translated.

### `has_entity_name` True (Mandatory for new integrations)

The entity's name property only identifies the data point (e.g., "Power usage") and should not include the device name. If the entity represents the single main feature of a device, its name property should typically return `None`.

The `friendly_name` and `entity_id` are generated as follows:
- **Member of a device, name is None**: `friendly_name = {device.name}`
- **Member of a device, name is "Battery"**: `friendly_name = {device.name} Battery`

## Property implementation

There are three ways to set entity properties:
1. **Property function**: Using `@property` methods.
2. **Entity class or instance attributes**: Setting `_attr_` prefixed attributes (e.g., `_attr_icon`).
3. **Entity description**: Using a dataclass (e.g., `SensorEntityDescription`) passed to the entity.

## Lifecycle hooks

- `async_added_to_hass()`: Called when an entity is assigned to Home Assistant but before it is written to the state machine.
- `async_will_remove_from_hass()`: Called when an entity is about to be removed.

## Icons

Home Assistant uses the Material Design Icons (MDI).
- **Icon translations**: Preferred. Uses `icons.json` to map states to icons.
- **Icon property**: Custom logic based on state or other factors.

## Excluding state attributes from recorder history

Use `_unrecorded_attributes` or `_entity_component_unrecorded_attributes` to prevent certain attributes (like large image URLs or frequently changing static data) from bloating the database.