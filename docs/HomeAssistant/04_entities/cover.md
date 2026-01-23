---
title: Cover entity
sidebar_label: Cover
---

A cover entity controls an opening or cover, such as a garage door or a window shade. Derive a platform entity from [`homeassistant.components.cover.CoverEntity`](https://github.com/home-assistant/core/blob/dev/homeassistant/components/cover/__init__.py).

:::note
The cover entity should only be used for devices that control an opening or cover.
For other types of devices entities such as [Number](/docs/core/entity/number) should be used instead, even if that has not been the case in the past.
:::

## Properties

:::tip
Properties should always only return information from memory and not do I/O (like network requests). Implement `update()` or `async_update()` to fetch data.
:::

| Name | Type | Default | Description
| ----------------------- | ---- | ------- | -----------
| current_cover_position | <code>int &#124; None</code> | `None` | The current position of cover where 0 means closed and 100 is fully open.
| current_cover_tilt_position | <code>int &#124; None</code> | `None` | The current tilt position of the cover where 0 means closed/no tilt and 100 means open/maximum tilt.
| is_closed | <code>bool &#124; None</code> | **Required** | If the cover is closed or not. Used to determine `state`.
| is_closing | <code>bool &#124; None</code> | `None` | If the cover is closing or not. Used to determine `state`.
| is_opening | <code>bool &#124; None</code> | `None` | If the cover is opening or not. Used to determine `state`.

### States

The state is defined by setting the above properties. The resulting state is using the `CoverState` enum to return one of the below members.

| Value       | Description                                                        |
|-------------|--------------------------------------------------------------------|
| `CLOSED`    | The cover is closed.                                                |
| `CLOSING`   | The cover is closing.                                               |
| `OPENING`   | The cover is opening.                                               |
| `OPEN`      | The cover is open.                                                  |

### Device classes

| Constant | Description
|----------|-----------------------|
| `CoverDeviceClass.AWNING` | Control of an awning, such as an exterior retractible window, door, or patio cover.
| `CoverDeviceClass.BLIND` | Control of blinds, which are linked slats that expand or collapse to cover an opening or may be tilted to partially cover an opening, such as window blinds.
| `CoverDeviceClass.CURTAIN` | Control of curtains or drapes, which is often fabric hung above a window or door that can be drawn open.
| `CoverDeviceClass.DAMPER` | Control of a mechanical damper that reduces air flow, sound, or light.
| `CoverDeviceClass.DOOR` | Control of a door that provides access to an area which is typically part of a structure.
| `CoverDeviceClass.GARAGE` | Control of a garage door that provides access to a garage.
| `CoverDeviceClass.GATE` | Control of a gate that provides access to a driveway or other area. Gates are found outside of a structure and are typically part of a fence.
| `CoverDeviceClass.SHADE` | Control of shades, which are a continuous plane of material or connected cells that expanded or collapsed over an opening, such as window shades.
| `CoverDeviceClass.SHUTTER` | Control of shutters, which are linked slats that swing out/in to cover an opening or may be tilted to partially cover an opening, such as indoor or exterior window shutters.
| `CoverDeviceClass.WINDOW` | Control of a physical window that opens and closes or may tilt.

## Supported features

Supported features are defined by using values in the `CoverEntityFeature` enum
and are combined using the bitwise or (`|`) operator.

| Value               | Description                                                                      |
| ------------------- | -------------------------------------------------------------------------------- |
| `OPEN`              | The cover supports being opened.                                                 |
| `CLOSE`             | The cover supports being closed.                                                 |
| `SET_POSITION`      | The cover supports moving to a specific position between opened and closed.      |
| `STOP`              | The cover supports stopping the current action (open, close, set position)       |
| `OPEN_TILT`         | The cover supports being tilting open.                                           |
| `CLOSE_TILT`        | The cover supports being tilting closed.                                         |
| `SET_TILT_POSITION` | The cover supports moving to a specific tilt position between opened and closed. |
| `STOP_TILT`         | The cover supports stopping the current tilt action (open, close, set position)  |

## Methods

### Open cover

Only implement this method if the flag `SUPPORT_OPEN` is set.

```python
class MyCover(CoverEntity):
    # Implement one of these methods.

    def open_cover(self, **kwargs):
        """Open the cover."""

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
```

### Close cover

Only implement this method if the flag `SUPPORT_CLOSE` is set.

```python
class MyCover(CoverEntity):
    # Implement one of these methods.

    def close_cover(self, **kwargs):
        """Close cover."""

    async def async_close_cover(self, **kwargs):
        """Close cover."""
```

### Set cover position

Only implement this method if the flag `SUPPORT_SET_POSITION` is set.

```python
class MyCover(CoverEntity):
    # Implement one of these methods.

    def set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
```

### Stop cover

Only implement this method if the flag `SUPPORT_STOP` is set.

```python
class MyCover(CoverEntity):
    # Implement one of these methods.

    def stop_cover(self, **kwargs):
        """Stop the cover."""

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
```

### Open cover tilt

Only implement this method if the flag `SUPPORT_OPEN_TILT` is set.

```python
class MyCover(CoverEntity):
    # Implement one of these methods.

    def open_cover_tilt(self, **kwargs):
        """Open the cover tilt."""

    async def async_open_cover_tilt(self, **kwargs):
        """Open the cover tilt."""
```

### Close cover tilt

Only implement this method if the flag `SUPPORT_CLOSE_TILT` is set.

```python
class MyCover(CoverEntity):
    # Implement one of these methods.

    def close_cover_tilt(self, **kwargs):
        """Close the cover tilt."""

    async def async_close_cover_tilt(self, **kwargs):
        """Close the cover tilt."""
```

### Set cover tilt position

Only implement this method if the flag `SUPPORT_SET_TILT_POSITION` is set.

```python
class MyCover(CoverEntity):
    # Implement one of these methods.

    def set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position."""

    async def async_set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position."""
```

### Stop cover tilt

Only implement this method if the flag `SUPPORT_STOP_TILT` is set.

```python
class MyCover(CoverEntity):
    # Implement one of these methods.

    def stop_cover_tilt(self, **kwargs):
        """Stop the cover."""

    async def async_stop_cover_tilt(self, **kwargs):
        """Stop the cover."""
```
