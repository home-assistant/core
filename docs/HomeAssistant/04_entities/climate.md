---
title: Climate entity
sidebar_label: Climate
---

A climate entity controls temperature, humidity, or fans, such as A/C systems and humidifiers. Derive a platform entity from [`homeassistant.components.climate.ClimateEntity`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/climate/__init__.py)

## Properties

:::tip
Properties should always only return information from memory and not do I/O (like network requests). Implement `update()` or `async_update()` to fetch data.
:::

| Name                    | Type                                | Default                              | Description                                                                |
| ----------------------- | ----------------------------------- | ------------------------------------ | -------------------------------------------------------------------------- |
| current_humidity        | <code>float &#124; None</code>        | `None`                               | The current humidity.                                                      |
| current_temperature     | <code>float &#124; None</code>      | `None`                               | The current temperature.                                                   |
| fan_mode                | <code>str &#124; None</code>        | **Required by SUPPORT_FAN_MODE**     | The current fan mode.                                                      |
| fan_modes               | <code>list[str] &#124; None</code>  | **Required by SUPPORT_FAN_MODE**     | The list of available fan modes.                                           |
| hvac_action             | <code>HVACAction &#124; None</code> | `None`                               | The current HVAC action (heating, cooling)                                 |
| hvac_mode               | <code>HVACMode &#124; None</code>   | **Required**                         | The current operation (e.g. heat, cool, idle). Used to determine `state`.  |
| hvac_modes              | <code>list[HVACMode]</code>         | **Required**                         | List of available operation modes. See below.                              |
| max_humidity            | `float`                               | `DEFAULT_MAX_HUMIDITY` (value == 99) | The maximum humidity.                                                      |
| max_temp                | `float`                             | `DEFAULT_MAX_TEMP` (value == 35 °C)  | The maximum temperature in `temperature_unit`.                             |
| min_humidity            | `float`                               | `DEFAULT_MIN_HUMIDITY` (value == 30) | The minimum humidity.                                                      |
| min_temp                | `float`                             | `DEFAULT_MIN_TEMP` (value == 7 °C)   | The minimum temperature in `temperature_unit`.                             |
| precision               | `float`                             | According to `temperature_unit`      | The precision of the temperature in the system. Defaults to tenths for TEMP_CELSIUS, whole number otherwise. |
| preset_mode             | <code>str &#124; None</code>        | **Required by SUPPORT_PRESET_MODE**  | The current active preset.                                                 |
| preset_modes            | <code>list[str] &#124; None</code>  | **Required by SUPPORT_PRESET_MODE**  | The available presets.                                                     |
| swing_mode              | <code>str &#124; None</code>        | **Required by SUPPORT_SWING_MODE**   | The swing setting.                                                         |
| swing_modes             | <code>list[str] &#124; None</code>  | **Required by SUPPORT_SWING_MODE**   | Returns the list of available swing modes, only vertical modes in the case horizontal swing is implemented. |
| swing_horizontal_mode | <code>str &#124; None</code>        | **Required by SUPPORT_SWING_HORIZONTAL_MODE**   | The horizontal swing setting.                                     |
| swing_horizontal_modes | <code>list[str] &#124; None</code>  | **Required by SUPPORT_SWING_HORIZONTAL_MODE**  | Returns the list of available horizontal swing modes.                                 |
| target_humidity         | <code>float &#124; None</code>        | `None`                               | The target humidity the device is trying to reach.                         |
| target_temperature      | <code>float &#124; None</code>      | `None`                               | The temperature currently set to be reached.                               |
| target_temperature_high | <code>float &#124; None</code>      | **Required by TARGET_TEMPERATURE_RANGE** | The upper bound target temperature                                     |
| target_temperature_low  | <code>float &#124; None</code>      | **Required by TARGET_TEMPERATURE_RANGE** | The lower bound target temperature                                     |
| target_temperature_step | <code>float &#124; None</code>      | `None`                               | The supported step size a target temperature can be increased or decreased |
| temperature_unit        | <code>str</code>                    | **Required**                         | The unit of temperature measurement for the system (`TEMP_CELSIUS` or `TEMP_FAHRENHEIT`).                    |

### HVAC modes

You are only allowed to use the built-in HVAC modes, provided by the `HVACMode`
enum. If you want another mode, add a preset instead.


| Name                 | Description                                                         |
| -------------------- | ------------------------------------------------------------------- |
| `HVACMode.OFF`       | The device is turned off.                                           |
| `HVACMode.HEAT`      | The device is set to heat to a target temperature.                  |
| `HVACMode.COOL`      | The device is set to cool to a target temperature.                  |
| `HVACMode.HEAT_COOL` | The device is set to heat/cool to a target temperature range.       |
| `HVACMode.AUTO`      | The device is set to a schedule, learned behavior, AI.              |
| `HVACMode.DRY`       | The device is set to dry/humidity mode.                             |
| `HVACMode.FAN_ONLY`  | The device only has the fan on. No heating or cooling taking place. |

### HVAC action

The HVAC action describes the _current_ action. This is different from the mode, because if a device is set to heat, and the target temperature is already achieved, the device will not be actively heating anymore. It is only allowed to use the built-in HVAC actions, provided by the `HVACAction` enum.

| Name                    | Description           |
| ----------------------- | --------------------- |
| `HVACAction.OFF`        | Device is turned off. |
| `HVACAction.PREHEATING` | Device is preheating. |
| `HVACAction.HEATING`    | Device is heating.    |
| `HVACAction.COOLING`    | Device is cooling.    |
| `HVACAction.DRYING`     | Device is drying.     |
| `HVACAction.FAN`        | Device has fan on.    |
| `HVACAction.IDLE`       | Device is idle.       |
| `HVACAction.DEFROSTING` | Device is defrosting. |

### Presets

A device can have different presets that it might want to show to the user. Common presets are "Away" or "Eco". There are a couple of built-in presets that will offer translations, but you're also allowed to add custom presets.

| Name       | Description                                            |
| ---------- | ------------------------------------------------------ |
| `NONE`     | No preset is active                                    |
| `ECO`      | Device is running an energy-saving mode                |
| `AWAY`     | Device is in away mode                                 |
| `BOOST`    | Device turn all valve full up                          |
| `COMFORT`  | Device is in comfort mode                              |
| `HOME`     | Device is in home mode                                 |
| `SLEEP`    | Device is prepared for sleep                           |
| `ACTIVITY` | Device is reacting to activity (e.g. movement sensors) |

### Fan modes

A device's fan can have different states. There are a couple of built-in fan modes, but you're also allowed to use custom fan modes.

| Name          |
| ------------- |
| `FAN_ON`      |
| `FAN_OFF`     |
| `FAN_AUTO`    |
| `FAN_LOW`     |
| `FAN_MEDIUM`  |
| `FAN_HIGH`    |
| `FAN_MIDDLE`  |
| `FAN_FOCUS`   |
| `FAN_DIFFUSE` |

### Swing modes

The device fan can have different swing modes that it wants the user to know about/control.

:::note

For integrations that don't have independent control of vertical and horizontal swing, all possible options should be listed in `swing_modes`, otherwise `swing_modes` provides vertical support and `swing_horizontal_modes` should provide horizontal support.

:::

| Name               | Description                                       |
| ------------------ | ------------------------------------------------- |
| `SWING_OFF`        | The fan is not swinging.                          |
| `SWING_ON`         | The fan is swinging.                              |
| `SWING_VERTICAL`   | The fan is swinging vertical.                     |
| `SWING_HORIZONTAL` | The fan is swinging horizontal.                   |
| `SWING_BOTH`       | The fan is swinging both horizontal and vertical. |

### Swing horizontal modes

The device fan can have different horizontal swing modes that it wants the user to know about/control.

:::note

This should only be implemented if the integration has independent control of vertical and horizontal swing. In such case the `swing_modes` property will provide vertical support and `swing_horizontal_modes` will provide horizontal support.

:::

| Name               | Description                                       |
| ------------------ | ------------------------------------------------- |
| `SWING_OFF`        | The fan is not swinging.                          |
| `SWING_ON`         | The fan is swinging.                              |

## Supported features

Supported features are defined by using values in the `ClimateEntityFeature` enum
and are combined using the bitwise or (`|`) operator.

| Value                      | Description                                                                                 |
| -------------------------- | ------------------------------------------------------------------------------------------- |
| `TARGET_TEMPERATURE`       | The device supports a target temperature.                                                   |
| `TARGET_TEMPERATURE_RANGE` | The device supports a ranged target temperature. Used for HVAC modes `heat_cool` and `auto` |
| `TARGET_HUMIDITY`          | The device supports a target humidity.                                                      |
| `FAN_MODE`                 | The device supports fan modes.                                                              |
| `PRESET_MODE`              | The device supports presets.                                                                |
| `SWING_MODE`               | The device supports swing modes.                                                            |
| `SWING_HORIZONTAL_MODE`    | The device supports horizontal swing modes.                                                            |
| `TURN_ON`                 | The device supports turn on.                                                      |
| `TURN_OFF`                 | The device supports turn off.                                                      |

## Methods

### Set HVAC mode

```python
class MyClimateEntity(ClimateEntity):
    # Implement one of these methods.

    def set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
```

### Turn on

```python
class MyClimateEntity(ClimateEntity):
    # Implement one of these methods.
    # The `turn_on` method should set `hvac_mode` to any other than
    # `HVACMode.OFF` by optimistically setting it from the service action
    # handler or with the next state update

    def turn_on(self):
        """Turn the entity on."""

    async def async_turn_on(self):
        """Turn the entity on."""
```

### Turn off

```python
class MyClimateEntity(ClimateEntity):
    # Implement one of these methods.
    # The `turn_off` method should set `hvac_mode` to `HVACMode.OFF` by
    # optimistically setting it from the service action handler or with the
    # next state update

    def turn_off(self):
        """Turn the entity off."""

    async def async_turn_off(self):
        """Turn the entity off."""
```

### Toggle

```python
class MyClimateEntity(ClimateEntity):
    # It's not mandatory to implement the `toggle` method as the base implementation
    # will call `turn_on`/`turn_off` according to the current HVAC mode.

    # If implemented, the `toggle` method should set `hvac_mode` to the right `HVACMode` by
    # optimistically setting it from the service action handler
    # or with the next state update.

    def toggle(self):
        """Toggle the entity."""

    async def async_toggle(self):
        """Toggle the entity."""
```

### Set preset mode

```python
class MyClimateEntity(ClimateEntity):
    # Implement one of these methods.

    def set_preset_mode(self, preset_mode):
        """Set new target preset mode."""

    async def async_set_preset_mode(self, preset_mode):
        """Set new target preset mode."""
```

### Set fan mode

```python
class MyClimateEntity(ClimateEntity):
    # Implement one of these methods.

    def set_fan_mode(self, fan_mode):
        """Set new target fan mode."""

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
```

### Set humidity

```python
class MyClimateEntity(ClimateEntity):
    # Implement one of these methods.

    def set_humidity(self, humidity):
        """Set new target humidity."""

    async def async_set_humidity(self, humidity):
        """Set new target humidity."""
```

### Set swing mode

```python
class MyClimateEntity(ClimateEntity):
    # Implement one of these methods.

    def set_swing_mode(self, swing_mode):
        """Set new target swing operation."""

    async def async_set_swing_mode(self, swing_mode):
        """Set new target swing operation."""
```

### Set horizontal swing mode

```python
class MyClimateEntity(ClimateEntity):
    # Implement one of these methods.

    def set_swing_horizontal_mode(self, swing_mode):
        """Set new target horizontal swing operation."""

    async def async_set_swing_horizontal_mode(self, swing_mode):
        """Set new target horizontal swing operation."""
```

### Set temperature

:::note
`ClimateEntity` has built-in validation to ensure that the `target_temperature_low` argument is lower than or equal to the `target_temperature_high` argument. Therefore, integrations do not need to validate this in their own implementation.
:::

```python
class MyClimateEntity(ClimateEntity):
    # Implement one of these methods.

    def set_temperature(self, **kwargs):
        """Set new target temperature."""

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
```
