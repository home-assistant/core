"""Platform for ICS-2000 integration."""

from __future__ import annotations

import logging
from typing import Any

from ics_2000.entities import switch_device

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HubConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HubConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Setup the switches."""

    async_add_entities(
        [
            Switch(entity, entry.runtime_data.local_address)
            for entity in entry.runtime_data.devices
            if type(entity) is switch_device.SwitchDevice
        ]
    )


class Switch(SwitchEntity):
    """Representation of an switches light."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self, switch: switch_device.SwitchDevice, local_address: str | None
    ) -> None:
        """Initialize an switch."""
        self._switch = switch
        self._name = str(switch.name)
        self._state = False  # self._switch.get_on_status()
        self._local_address = local_address

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._switch.device_data.id)},
            name=self.name,
            model=self._switch.device_config.model_name,
            model_id=str(self._switch.device_data.device),
            sw_version=str(
                self._switch.device_data.data.get("module", {}).get("version", "")
            ),
        )

    @property
    def icon(self) -> str | None:
        """Icon of the entity."""
        return "mdi:flash"

    @property
    def name(self) -> str:
        """Return the display name of this switch."""
        return self._name

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        return self._state

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the switch to turn on."""
        await self.hass.async_add_executor_job(
            self._switch.turn_on, self._local_address is not None
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the switch to turn off."""
        await self.hass.async_add_executor_job(
            self._switch.turn_off, self._local_address is not None
        )

    async def async_update(self) -> None:
        """Fetch new state data for this switch."""
        self._state = await self.hass.async_add_executor_job(self._switch.get_on_status)
