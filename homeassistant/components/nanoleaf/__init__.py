"""The Nanoleaf integration."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.components.nanoleaf.util import get_local_ip
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .aionanoleaf import Event, InvalidToken, Nanoleaf, TouchEvent, Unavailable
from .const import DOMAIN
from .light import NanoleafLight
from .sensor import NanoleafPanelTouchStrength

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nanoleaf from a config entry."""
    nanoleaf = Nanoleaf(
        async_get_clientsession(hass), entry.data[CONF_HOST], entry.data[CONF_TOKEN]
    )
    try:
        await nanoleaf.get_info()
    except Unavailable as err:
        raise ConfigEntryNotReady from err
    except InvalidToken as err:
        raise ConfigEntryAuthFailed from err

    # device: [entry_id, Nanoleaf], light_entity: [serial_no, Entity], panel_entity[serial_no, [panel_id, Entity]]
    hass.data.setdefault(
        DOMAIN, {"device": {}, "light_entity": {}, "panel_entity": {}}
    )["device"][entry.entry_id] = nanoleaf
    hass.data[DOMAIN]["panel_entity"][nanoleaf.serial_no] = {}

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "light")
    )

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )

    async def state_update_callback(event: Event) -> None:
        """Receive state and effect event."""
        light_entity: NanoleafLight | None = hass.data[DOMAIN]["light_entity"].get(
            nanoleaf.serial_no
        )
        if light_entity is not None:
            light_entity.async_write_ha_state()

    async def touch_callback(event: TouchEvent) -> None:
        """Receive touch event."""
        event_data = {
            "device_id": nanoleaf.serial_no,
            "type": "touch",
            "panel_id": event.panel_id,
            "gesture": event.gesture,
        }
        hass.bus.async_fire(f"{DOMAIN}_event", event_data)

    async def advanced_touch_callback(
        panel_id: int, gesture: str, strength: int, panel_id2: int
    ) -> None:
        """Receive touch event."""
        event_data = {
            "device_id": nanoleaf.serial_no,
            "type": "advanced_touch",
            "panel_id": panel_id,
            "gesture": gesture,
            "strength": strength,
            "swipe_to_panel_id": panel_id2,
        }
        hass.bus.async_fire(f"{DOMAIN}_event", event_data)

        panel_entity: NanoleafPanelTouchStrength | None = hass.data[DOMAIN][
            "panel_entity"
        ][nanoleaf.serial_no].get(panel_id)
        if panel_entity is not None:
            await panel_entity.async_set_state(strength)

    # Find the Home Assistant IP to open the UDP socket
    local_ip = await get_local_ip(hass, entry, nanoleaf)

    local_port: int | None = entry.options.get("local_port")

    asyncio.create_task(
        nanoleaf.listen_events(
            state_callback=state_update_callback,
            effects_callback=state_update_callback,
            touch_callback=touch_callback,
            advanced_touch_callback=advanced_touch_callback,
            local_ip=local_ip,
            local_port=local_port,
        )
    )

    return True
