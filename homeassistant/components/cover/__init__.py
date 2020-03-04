"""Support for Cover devices."""
from datetime import timedelta
import functools as ft
import logging
from typing import Any

import voluptuous as vol

from homeassistant.const import (
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER,
    SERVICE_STOP_COVER_TILT,
    SERVICE_TOGGLE,
    SERVICE_TOGGLE_COVER_TILT,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.loader import bind_hass

# mypy: allow-untyped-calls, allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)

DOMAIN = "cover"
SCAN_INTERVAL = timedelta(seconds=15)

ENTITY_ID_FORMAT = DOMAIN + ".{}"

# Refer to the cover dev docs for device class descriptions
DEVICE_CLASS_AWNING = "awning"
DEVICE_CLASS_BLIND = "blind"
DEVICE_CLASS_CURTAIN = "curtain"
DEVICE_CLASS_DAMPER = "damper"
DEVICE_CLASS_DOOR = "door"
DEVICE_CLASS_GARAGE = "garage"
DEVICE_CLASS_SHADE = "shade"
DEVICE_CLASS_SHUTTER = "shutter"
DEVICE_CLASS_WINDOW = "window"
DEVICE_CLASSES = [
    DEVICE_CLASS_AWNING,
    DEVICE_CLASS_BLIND,
    DEVICE_CLASS_CURTAIN,
    DEVICE_CLASS_DAMPER,
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_GARAGE,
    DEVICE_CLASS_SHADE,
    DEVICE_CLASS_SHUTTER,
    DEVICE_CLASS_WINDOW,
]
DEVICE_CLASSES_SCHEMA = vol.All(vol.Lower, vol.In(DEVICE_CLASSES))

SUPPORT_OPEN = 1
SUPPORT_CLOSE = 2
SUPPORT_SET_POSITION = 4
SUPPORT_STOP = 8
SUPPORT_OPEN_TILT = 16
SUPPORT_CLOSE_TILT = 32
SUPPORT_STOP_TILT = 64
SUPPORT_SET_TILT_POSITION = 128

ATTR_CURRENT_POSITION = "current_position"
ATTR_CURRENT_TILT_POSITION = "current_tilt_position"
ATTR_POSITION = "position"
ATTR_TILT_POSITION = "tilt_position"


@bind_hass
def is_closed(hass, entity_id):
    """Return if the cover is closed based on the statemachine."""
    return hass.states.is_state(entity_id, STATE_CLOSED)


async def async_setup(hass, config):
    """Track states and offer events for covers."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    await component.async_setup(config)

    component.async_register_entity_service(SERVICE_OPEN_COVER, {}, "async_open_cover")

    component.async_register_entity_service(
        SERVICE_CLOSE_COVER, {}, "async_close_cover"
    )

    component.async_register_entity_service(
        SERVICE_SET_COVER_POSITION,
        {
            vol.Required(ATTR_POSITION): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            )
        },
        "async_set_cover_position",
    )

    component.async_register_entity_service(SERVICE_STOP_COVER, {}, "async_stop_cover")

    component.async_register_entity_service(SERVICE_TOGGLE, {}, "async_toggle")

    component.async_register_entity_service(
        SERVICE_OPEN_COVER_TILT, {}, "async_open_cover_tilt"
    )

    component.async_register_entity_service(
        SERVICE_CLOSE_COVER_TILT, {}, "async_close_cover_tilt"
    )

    component.async_register_entity_service(
        SERVICE_STOP_COVER_TILT, {}, "async_stop_cover_tilt"
    )

    component.async_register_entity_service(
        SERVICE_SET_COVER_TILT_POSITION,
        {
            vol.Required(ATTR_TILT_POSITION): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            )
        },
        "async_set_cover_tilt_position",
    )

    component.async_register_entity_service(
        SERVICE_TOGGLE_COVER_TILT, {}, "async_toggle_tilt"
    )

    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)


class CoverDevice(Entity):
    """Representation of a cover."""

    @property
    def current_cover_position(self):
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        pass

    @property
    def current_cover_tilt_position(self):
        """Return current position of cover tilt.

        None is unknown, 0 is closed, 100 is fully open.
        """
        pass

    @property
    def state(self):
        """Return the state of the cover."""
        if self.is_opening:
            return STATE_OPENING
        if self.is_closing:
            return STATE_CLOSING

        closed = self.is_closed

        if closed is None:
            return None

        return STATE_CLOSED if closed else STATE_OPEN

    @property
    def state_attributes(self):
        """Return the state attributes."""
        data = {}

        current = self.current_cover_position
        if current is not None:
            data[ATTR_CURRENT_POSITION] = self.current_cover_position

        current_tilt = self.current_cover_tilt_position
        if current_tilt is not None:
            data[ATTR_CURRENT_TILT_POSITION] = self.current_cover_tilt_position

        return data

    @property
    def supported_features(self):
        """Flag supported features."""
        supported_features = SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP

        if self.current_cover_position is not None:
            supported_features |= SUPPORT_SET_POSITION

        if self.current_cover_tilt_position is not None:
            supported_features |= (
                SUPPORT_OPEN_TILT
                | SUPPORT_CLOSE_TILT
                | SUPPORT_STOP_TILT
                | SUPPORT_SET_TILT_POSITION
            )

        return supported_features

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        pass

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        pass

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        raise NotImplementedError()

    def open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        raise NotImplementedError()

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        await self.hass.async_add_job(ft.partial(self.open_cover, **kwargs))

    def close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        raise NotImplementedError()

    async def async_close_cover(self, **kwargs):
        """Close cover."""
        await self.hass.async_add_job(ft.partial(self.close_cover, **kwargs))

    def toggle(self, **kwargs: Any) -> None:
        """Toggle the entity."""
        if self.is_closed:
            self.open_cover(**kwargs)
        else:
            self.close_cover(**kwargs)

    async def async_toggle(self, **kwargs):
        """Toggle the entity."""
        if self.is_closed:
            await self.async_open_cover(**kwargs)
        else:
            await self.async_close_cover(**kwargs)

    def set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        pass

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        await self.hass.async_add_job(ft.partial(self.set_cover_position, **kwargs))

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        pass

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        await self.hass.async_add_job(ft.partial(self.stop_cover, **kwargs))

    def open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        pass

    async def async_open_cover_tilt(self, **kwargs):
        """Open the cover tilt."""
        await self.hass.async_add_job(ft.partial(self.open_cover_tilt, **kwargs))

    def close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt."""
        pass

    async def async_close_cover_tilt(self, **kwargs):
        """Close the cover tilt."""
        await self.hass.async_add_job(ft.partial(self.close_cover_tilt, **kwargs))

    def set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position."""
        pass

    async def async_set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position."""
        await self.hass.async_add_job(
            ft.partial(self.set_cover_tilt_position, **kwargs)
        )

    def stop_cover_tilt(self, **kwargs):
        """Stop the cover."""
        pass

    async def async_stop_cover_tilt(self, **kwargs):
        """Stop the cover."""
        await self.hass.async_add_job(ft.partial(self.stop_cover_tilt, **kwargs))

    def toggle_tilt(self, **kwargs: Any) -> None:
        """Toggle the entity."""
        if self.current_cover_tilt_position == 0:
            self.open_cover_tilt(**kwargs)
        else:
            self.close_cover_tilt(**kwargs)

    async def async_toggle_tilt(self, **kwargs):
        """Toggle the entity."""
        if self.current_cover_tilt_position == 0:
            await self.async_open_cover_tilt(**kwargs)
        else:
            await self.async_close_cover_tilt(**kwargs)
