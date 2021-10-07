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
from .binary_sensor import NanoleafPanelHover, NanoleafPanelTouch
from .const import DOMAIN
from .light import NanoleafLight
from .sensor import NanoleafPanelTouchStrength

PLATFORMS = ["light", "sensor", "binary_sensor"]

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

    # hass.data[DOMAIN] = {
    #   "device": {  # Used to setup the platforms and entities
    #     entry_id: Nanoleaf
    #   },
    #   "entity": {  # Used for touch events and push updates
    #     serial_no: {
    #       "light": LightEntity,
    #       "touch": BinarySensorEntity,
    #       "hold": BinarySensorEntity,
    #       "strength": SensorEntity
    #     }
    #   }
    # }
    hass.data.setdefault(
        DOMAIN,
        {
            "device": {},
            "light_entity": {},
            "panel_strength_entity": {},
            "panel_touch_entity": {},
            "panel_hover_entity": {},
        },
    )["device"][entry.entry_id] = nanoleaf
    hass.data[DOMAIN]["panel_strength_entity"][nanoleaf.serial_no] = {}
    hass.data[DOMAIN]["panel_touch_entity"][nanoleaf.serial_no] = {}
    hass.data[DOMAIN]["panel_hover_entity"][nanoleaf.serial_no] = {}

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    async def update_light_state(event: Event) -> None:
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
            "swipe_to_panel_id": None,
        }
        hass.bus.async_fire(f"{DOMAIN}_event", event_data)

    async def advanced_touch_callback(
        panel_id: int, gesture: str, strength: int, panel_id2: int
    ) -> None:
        """Receive touch event."""
        panel_touch_entity: NanoleafPanelTouch | None = hass.data[DOMAIN][
            "panel_touch_entity"
        ][nanoleaf.serial_no].get(panel_id)
        if panel_touch_entity is not None:
            await panel_touch_entity.async_set_state(
                True if gesture == "Hold" or gesture == "Down" else False
            )

        panel_hover_entity: NanoleafPanelHover | None = hass.data[DOMAIN][
            "panel_hover_entity"
        ][nanoleaf.serial_no].get(panel_id)
        if panel_hover_entity is not None:
            await panel_hover_entity.async_set_state(
                True if gesture == "Hover" or gesture == "Up" else False
            )

        if gesture == "Hold" or gesture == "Hover":
            panel_strength_entity: NanoleafPanelTouchStrength | None = hass.data[
                DOMAIN
            ]["panel_strength_entity"][nanoleaf.serial_no].get(panel_id)
            if panel_strength_entity is not None:
                await panel_strength_entity.async_set_state(strength)
        if gesture not in ("Hold", "Hover", "Down", "Up"):
            # Only send an event for gestures that are not represented as entities
            event_data = {
                "device_id": nanoleaf.serial_no,
                "type": "touch",
                "panel_id": panel_id,
                "gesture": gesture,
                "strength": strength if gesture == "Swipe" else None,
                "swipe_to_panel_id": panel_id2 if gesture == "Swipe" else None,
            }
            hass.bus.async_fire(f"{DOMAIN}_event", event_data)

    # Find the Home Assistant IP to open the UDP socket
    try:
        local_ip = await get_local_ip(hass, entry, nanoleaf)
    except ValueError:
        _LOGGER.error(
            "Couldn't determine your Home Assistant IP, select an IP in the integration configuration"
        )
        return False

    # A random available port is used if port is None
    local_port: int | None = entry.options.get("local_port")

    asyncio.create_task(
        nanoleaf.listen_events(
            state_callback=update_light_state,
            effects_callback=update_light_state,
            touch_callback=touch_callback,
            advanced_touch_callback=advanced_touch_callback,
            local_ip=local_ip,
            local_port=local_port,
        )
    )

    return True
