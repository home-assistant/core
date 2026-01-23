---
title: Fan entity
sidebar_label: Fan
---

A fan entity is a device that controls the different vectors of your fan such as speed, direction and oscillation. Derive entity platforms from ['homeassistant.components.fan.FanEntity'](https://github.com/home-assistant/core/blob/dev/homeassistant/components/fan/__init__.py).

## Properties

:::tip
Properties should always only return information from memory and not do I/O (like network requests). Implement `update()` or `async_update()` to fetch data.
:::

| Name | Type | Default | Description
| ---- | ---- | ------- | -----------
| current_direction  | <code>str &#124; None</code>       | `None` | The current direction of the fan.                                                                       |
| is_on              | <code>bool &#124; None</code>      | `None` | True if the fan is on.                                                                                  |
| oscillating        | <code>bool &#124; None</code>       | `None` | True if the fan is oscillating.                                                                         |
| percentage         | <code>int &#124; None</code>       | `0`    | The current speed percentage. Must be a value between 0 (off) and 100.                                  |
| preset_mode        | <code>str &#124; None</code>       | `None` | The current preset_mode. One of the values in `preset_modes` or `None` if no preset is active.          |
| preset_modes       | <code>list[str] &#124; None</code> | `None` | The list of supported preset_modes. This is an arbitrary list of str and should not contain any speeds. |
| speed_count        | `int`                              | 100    | The number of speeds the fan supports.                                                                  |

### Preset modes

A fan may have preset modes that automatically control the percentage speed or other functionality. Common examples include `auto`, `smart`, `whoosh`, `eco`, and `breeze`. If no preset mode is set, the `preset_mode` property must be set to `None`.

Preset modes should not include named (manual) speed settings as these should be represented as percentages.

Manually setting a speed must disable any set preset mode. If it is possible to set a percentage speed manually without disabling the preset mode, create a switch or service action to represent the mode.

## Supported features

Supported features are defined by using values in the `FanEntityFeature` enum
and are combined using the bitwise or (`|`) operator.

| Value         | Description                                                              |
| ------------- | ------------------------------------------------------------------------ |
| `DIRECTION`   | The fan supports changing the direction.                                 |
| `OSCILLATE`   | The fan supports oscillation.                                            |
| `PRESET_MODE` | The fan supports preset modes.                                           |
| `SET_SPEED`   | The fan supports setting the speed percentage and optional preset modes. |
| `TURN_OFF`    | The fan supports turning off.                                                                                |
| `TURN_ON`     | The fan supports turning on.                                                                                 |

## Methods

### Set direction

Only implement this method if the flag `FanEntityFeature.DIRECTION` is set.

```python
class FanEntity(ToggleEntity):
    # Implement one of these methods.

    def set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""

    async def async_set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
```

### Set preset mode

Only implement this method if the flag `FanEntityFeature.PRESET_MODE` is set.

```python
class FanEntity(ToggleEntity):
    # Implement one of these methods.

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
```

### Set speed percentage

Only implement this method if the flag `FanEntityFeature.SET_SPEED` is set.

```python
class FanEntity(ToggleEntity):
    # Implement one of these methods.

    def set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
```

:::tip Converting speeds

Home Assistant includes a utility to convert speeds.

If the device has a list of named speeds:

```python
from homeassistant.util.percentage import ordered_list_item_to_percentage, percentage_to_ordered_list_item

ORDERED_NAMED_FAN_SPEEDS = ["one", "two", "three", "four", "five", "six"]  # off is not included

percentage = ordered_list_item_to_percentage(ORDERED_NAMED_FAN_SPEEDS, "three")

named_speed = percentage_to_ordered_list_item(ORDERED_NAMED_FAN_SPEEDS, 23)

...

    @property
    def percentage(self) -> Optional[int]:
        """Return the current speed percentage."""
        return ordered_list_item_to_percentage(ORDERED_NAMED_FAN_SPEEDS, current_speed)

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return len(ORDERED_NAMED_FAN_SPEEDS)
```

If the device has a numeric range of speeds:

```python
from homeassistant.util.percentage import ranged_value_to_percentage, percentage_to_ranged_value
from homeassistant.util.scaling import int_states_in_range

SPEED_RANGE = (1, 255)  # off is not included

percentage = ranged_value_to_percentage(SPEED_RANGE, 127)

value_in_range = math.ceil(percentage_to_ranged_value(SPEED_RANGE, 50))

...

    @property
    def percentage(self) -> Optional[int]:
        """Return the current speed percentage."""
        return ranged_value_to_percentage(SPEED_RANGE, current_speed)

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return int_states_in_range(SPEED_RANGE)
```
:::

### Turn on

Only implement this method if the flag `FanEntityFeature.TURN_ON` is set.

```python
class FanEntity(ToggleEntity):
    # Implement one of these methods.

    def turn_on(self, speed: Optional[str] = None, percentage: Optional[int] = None, preset_mode: Optional[str] = None, **kwargs: Any) -> None:
        """Turn on the fan."""

    async def async_turn_on(self, speed: Optional[str] = None, percentage: Optional[int] = None, preset_mode: Optional[str] = None, **kwargs: Any) -> None:
        """Turn on the fan."""
```

:::tip `speed` is deprecated.

For new integrations, `speed` should not be implemented and only `percentage` and `preset_mode` should be used.

:::

### Turn off

Only implement this method if the flag `FanEntityFeature.TURN_OFF` is set.

```python
class FanEntity(ToggleEntity):
    # Implement one of these methods.

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
```

### Toggle

Optional. If not implemented will default to checking what method to call using the is_on property.
Only implement this method if the flags `FanEntityFeature.TURN_ON` and `FanEntityFeature.TURN_OFF` are set.

```python
class FanEntity(ToggleEntity):
    # Implement one of these methods.

    def toggle(self, **kwargs: Any) -> None:
        """Toggle the fan."""

    async def async_toggle(self, **kwargs: Any) -> None:
        """Toggle the fan."""
```

### Oscillate

Only implement this method if the flag `FanEntityFeature.OSCILLATE` is set.

```python
class FanEntity(ToggleEntity):
    # Implement one of these methods.

    def oscillate(self, oscillating: bool) -> None:
        """Oscillate the fan."""

    async def async_oscillate(self, oscillating: bool) -> None:
        """Oscillate the fan."""
```
