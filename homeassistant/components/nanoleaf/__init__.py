"""The Nanoleaf integration."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging

from aionanoleaf import (
    EffectsEvent,
    InvalidToken,
    Nanoleaf,
    StateEvent,
    TouchEvent,
    Unavailable,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_TOKEN,
    CONF_TYPE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, NANOLEAF_EVENT, TOUCH_GESTURE_TRIGGER_MAP, TOUCH_MODELS

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BUTTON, Platform.LIGHT]


@dataclass
class NanoleafEntryData:
    """Class for sharing data within the Nanoleaf integration."""

    device: Nanoleaf
    coordinator: DataUpdateCoordinator[None]
    event_listener: asyncio.Task


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nanoleaf from a config entry."""
    nanoleaf = Nanoleaf(
        async_get_clientsession(hass), entry.data[CONF_HOST], entry.data[CONF_TOKEN]
    )

    async def async_get_state() -> None:
        """Get the state of the device."""
        try:
            await nanoleaf.get_info()
        except Unavailable as err:
            raise UpdateFailed from err
        except InvalidToken as err:
            raise ConfigEntryAuthFailed from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=entry.title,
        update_interval=timedelta(minutes=1),
        update_method=async_get_state,
    )

    await coordinator.async_config_entry_first_refresh()

    async def light_event_callback(event: StateEvent | EffectsEvent) -> None:
        """Receive state and effect event."""
        coordinator.async_set_updated_data(None)

    if supports_touch := nanoleaf.model in TOUCH_MODELS:
        device_registry = dr.async_get(hass)
        device_entry = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, nanoleaf.serial_no)},
        )

        async def touch_event_callback(event: TouchEvent) -> None:
            """Receive touch event."""
            gesture_type = TOUCH_GESTURE_TRIGGER_MAP.get(event.gesture_id)
            if gesture_type is None:
                _LOGGER.warning(
                    "Received unknown touch gesture ID %s", event.gesture_id
                )
                return
            _LOGGER.debug("Received touch gesture %s", gesture_type)
            hass.bus.async_fire(
                NANOLEAF_EVENT,
                {CONF_DEVICE_ID: device_entry.id, CONF_TYPE: gesture_type},
            )

    event_listener = asyncio.create_task(
        nanoleaf.listen_events(
            state_callback=light_event_callback,
            effects_callback=light_event_callback,
            touch_callback=touch_event_callback if supports_touch else None,
        )
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = NanoleafEntryData(
        nanoleaf, coordinator, event_listener
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    entry_data: NanoleafEntryData = hass.data[DOMAIN].pop(entry.entry_id)
    entry_data.event_listener.cancel()
    return True
