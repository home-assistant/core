---
title: Switch entity
sidebar_label: Switch
---

A switch entity turns on or off something, for example a relay. Derive a platform entity from [`homeassistant.components.switch.SwitchEntity`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/switch/__init__.py).
To represent something which has an on or off state but can't be controlled, for example a wall switch which transmits its state but can't be turned on or off from Home Assistant, a Binary Sensor is a better choice.
To represent something which doesn't have a state, for example a door bell push button, a custom event or a Device Trigger is a better choice.

## Properties

:::tip
Properties should always only return information from memory and not do I/O (like network requests). Implement `update()` or `async_update()` to fetch data.
:::

| Name | Type | Default | Description
| ---- | ---- | ------- | -----------
| is_on | boolean | `None` | If the switch is currently on or off.

## Methods

### Turn on

Turn the switch on.

```python
class MySwitch(SwitchEntity):
    # Implement one of these methods.

    def turn_on(self, **kwargs) -> None:
        """Turn the entity on."""

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
```

### Turn off

Turn the switch off.

```python
class MySwitch(SwitchEntity):
    # Implement one of these methods.

    def turn_off(self, **kwargs):
        """Turn the entity off."""

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
```

### Toggle

Optional. If not implemented will default to checking what method to call using the `is_on` property.

```python
class MySwitch(SwitchEntity):
    # Implement one of these methods.

    def toggle(self, **kwargs):
        """Toggle the entity."""

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""
```

### Available device classes

Optional. What type of device this. It will possibly map to google device types.

| Constant | Description
| ----- | -----------
| `SwitchDeviceClass.OUTLET` | Device is an outlet for power.
| `SwitchDeviceClass.SWITCH` | Device is switch for some type of entity.
