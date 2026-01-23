---
title: Humidifier entity
sidebar_label: Humidifier
---

A humidifier entity is a device whose main purpose is to control humidity, i.e. a humidifier or dehumidifier. Derive entity platforms from [`homeassistant.components.humidifier.HumidifierEntity`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/humidifier/__init__.py)

## Properties

:::tip
Properties should always only return information from memory and not do I/O (like network requests). Implement `update()` or `async_update()` to fetch data.
:::

| Name                    | Type                                           | Default                               | Description                                        |
| ----------------------- | ---------------------------------------------- | ------------------------------------- | -------------------------------------------------- |
| action                  | <code>HumidifierAction &#124; None</code>      | `None`                                | Returns the current status of the device.          |
| available_modes         | <code>list[str] &#124; None</code>             | **Required by MODES**                 | The available modes. Requires `SUPPORT_MODES`.     |
| current_humidity        | <code>float &#124; None</code>                   | `None`                                | The current humidity measured by the device.       |
| device_class            | <code>HumidifierDeviceClass &#124; None</code> | `None`                                | Type of hygrostat                                  |
| is_on                   | <code>bool &#124; None</code>                  | `None`                                | Whether the device is on or off.                   |
| max_humidity            | `float`                                          | `DEFAULT_MAX_HUMIDITY` (value == 100) | The maximum humidity.                              |
| min_humidity            | `float`                                          | `DEFAULT_MIN_HUMIDITY` (value == 0)   | The minimum humidity.                              |
| mode                    | <code>str &#124; None</code>                   | **Required**                          | The current active mode. Requires `SUPPORT_MODES`. |
| target_humidity         | <code>float &#124; None</code>                   | `None`                                | The target humidity the device is trying to reach. |
| target_humidity_step    | <code>float &#124; None</code>                   | `None`                                | The supported step size a target humidity can be increased or decreased. |

### Available device classes

| Constant                             | Description                                |
| ------------------------------------ | ------------------------------------------ |
| `HumidifierDeviceClass.DEHUMIDIFIER` | A dehumidifier                             |
| `HumidifierDeviceClass.HUMIDIFIER`   | A humidifier                               |


### Modes

A device can have different modes of operation that it might want to show to the user. They could be viewed as presets or some device states with reduced or enhanced functionality for special conditions, i.e. "auto" or "baby". There are a couple of built-in modes that will offer translations, but you're also allowed to add custom modes if that better represents the device.

| Name           | Description                              |
| -------------- | ---------------------------------------  |
| `MODE_NORMAL`  | No preset is active, normal operation    |
| `MODE_ECO`     | Device is running an energy-saving mode  |
| `MODE_AWAY`    | Device is in away mode                   |
| `MODE_BOOST`   | Device turn all valve full up            |
| `MODE_COMFORT` | Device is in comfort mode                |
| `MODE_HOME`    | Device is in home mode                   |
| `MODE_SLEEP`   | Device is prepared for sleep             |
| `MODE_AUTO`    | Device is controlling humidity by itself |
| `MODE_BABY`    | Device is trying to optimize for babies  |

## Supported features

Supported features are defined by using values in the `HumidifierEntityFeature` enum
and are combined using the bitwise or (`|`) operator.

| Value   | Description                          |
| ------- | ------------------------------------ |
| `MODES` | The device supports different modes. |

## Action

The `action` property may return the current operating state of the device, whether it is humidifying or idle. This is an informational property. Please note that when the device is off, the `action` attribute, if present, will automatically be replaced with "off". Also, please note that setting `action` to `off` does not replace the `is_on` property.

Current values for `HumidifierAction`:

| Name          | Description                                |
| ------------- | ------------------------------------------ |
| `HUMIDIFYING` | The device is currently humidifying.       |
| `DRYING`      | The device is currently dehumidifying.     |
| `IDLE`        | The device is on but not active right now. |
| `OFF`         | The device is switched off.                |

## Methods

### Set mode

```python
class MyHumidifierEntity(HumidifierEntity):
    # Implement one of these methods.

    def set_mode(self, mode):
        """Set new target preset mode."""

    async def async_set_mode(self, mode):
        """Set new target preset mode."""
```

### Set humidity

If the current mode does not allow to adjust target humidity, the device should automatically change its mode to the one which makes it possible upon this call.

```python
class MyHumidifierEntity(HumidifierEntity):
    # Implement one of these methods.

    def set_humidity(self, humidity):
        """Set new target humidity."""

    async def async_set_humidity(self, humidity):
        """Set new target humidity."""
```

### Turn on

```python
class MyHumidifierEntity(HumidifierEntity):
    # Implement one of these methods.

    def turn_on(self, **kwargs):
        """Turn the device on."""

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
```

### Turn off

```python
class MyHumidifierEntity(HumidifierEntity):
    # Implement one of these methods.

    def turn_off(self, **kwargs):
        """Turn the device off."""

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
```
