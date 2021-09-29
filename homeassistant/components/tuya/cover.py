"""Support for Tuya Cover."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.cover import (
    DEVICE_CLASS_CURTAIN,
    DOMAIN as DEVICE_DOMAIN,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    SUPPORT_STOP,
    CoverEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .base import TuyaHaEntity
from .const import (
    DOMAIN,
    TUYA_DEVICE_MANAGER,
    TUYA_DISCOVERY_NEW,
    TUYA_HA_DEVICES,
    TUYA_HA_TUYA_MAP,
)

_LOGGER = logging.getLogger(__name__)

TUYA_SUPPORT_TYPE = {"cl", "clkg"}  # Curtain  # Curtain Switch

# Curtain
# https://developer.tuya.com/en/docs/iot/f?id=K9gf46o5mtfyc
DPCODE_CONTROL = "control"
DPCODE_PERCENT_CONTROL = "percent_control"
DPCODE_PERCENT_STATE = "percent_state"
DPCODE_SITUATION_SET = "situation_set"

ATTR_POSITION = "position"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up tuya cover dynamically through tuya discovery."""
    hass.data[DOMAIN][entry.entry_id][TUYA_HA_TUYA_MAP][
        DEVICE_DOMAIN
    ] = TUYA_SUPPORT_TYPE

    async def async_discover_device(dev_ids: list[str]) -> None:
        """Discover and add a discovered tuya cover."""
        _LOGGER.debug("cover add-> %s", dev_ids)
        if not dev_ids:
            return
        entities = _setup_entities(hass, entry, dev_ids)
        async_add_entities(entities)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, TUYA_DISCOVERY_NEW.format(DEVICE_DOMAIN), async_discover_device
        )
    )

    device_manager = hass.data[DOMAIN][entry.entry_id][TUYA_DEVICE_MANAGER]
    device_ids = []
    for (device_id, device) in device_manager.device_map.items():
        if device.category in TUYA_SUPPORT_TYPE:
            device_ids.append(device_id)
    await async_discover_device(device_ids)


def _setup_entities(
    hass: HomeAssistant, entry: ConfigEntry, device_ids: list[str]
) -> list[Entity]:
    """Set up Tuya Cover."""
    device_manager = hass.data[DOMAIN][entry.entry_id][TUYA_DEVICE_MANAGER]
    entities: list[Entity] = []
    for device_id in device_ids:
        device = device_manager.device_map[device_id]
        if device is None:
            continue
        entities.append(TuyaHaCover(device, device_manager))
        hass.data[DOMAIN][entry.entry_id][TUYA_HA_DEVICES].add(device_id)
    return entities


class TuyaHaCover(TuyaHaEntity, CoverEntity):
    """Tuya Switch Device."""

    _attr_device_class = DEVICE_CLASS_CURTAIN

    @property
    def is_closed(self) -> bool | None:
        """Return is cover is closed."""
        return None

    @property
    def current_cover_position(self) -> int:
        """Return cover current position."""
        position = self.tuya_device.status.get(DPCODE_PERCENT_STATE, 0)
        if DPCODE_SITUATION_SET not in self.tuya_device.status:
            return 1 + int(0.98 * (100 - position))
        if self.tuya_device.status.get(DPCODE_SITUATION_SET) == "fully_open":
            return 1 + 0.98 * position
        
        return 1 + int(0.98 * (100 - position))

    def open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        self._send_command([{"code": DPCODE_CONTROL, "value": "open"}])

    def close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        self._send_command([{"code": DPCODE_CONTROL, "value": "close"}])

    def stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        self._send_command([{"code": DPCODE_CONTROL, "value": "stop"}])

    def set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        _LOGGER.debug("cover--> %s", kwargs)
        self._send_command(
            [{"code": DPCODE_PERCENT_CONTROL, "value": kwargs[ATTR_POSITION]}]
        )

    @property
    def supported_features(self):
        """Flag supported features."""
        supports = SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP

        if DPCODE_PERCENT_CONTROL in self.tuya_device.status:
            supports = supports | SUPPORT_SET_POSITION

        return supports
