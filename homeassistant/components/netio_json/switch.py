"""Platform for switch integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NetioDeviceEntity
from .const import DATA_NETIO_CLIENT, DOMAIN
from .pdu import NetioPDU

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up NetIO PDU Sensors from Config Entry."""
    _LOGGER.info("Async setup entry in sensor")
    pdu = hass.data[DOMAIN][config_entry.entry_id][DATA_NETIO_CLIENT]
    if pdu.read_only:
        return

    switches = []

    for output in range(pdu.output_count()):
        switches.append(NetioSwitch(pdu, config_entry, output + 1))

    async_add_entities(switches, True)


class NetioSwitch(NetioDeviceEntity, SwitchEntity):
    """Representation of a NetIO Output."""

    def __init__(
        self,
        pdu: NetioPDU,
        config_entry: ConfigEntry,
        outlet: int,
        enabled_default: bool = True,
    ) -> None:
        """Initialize NetIO PDU Output."""
        self._state: int | str | float | None = None
        self.outlet = outlet
        name = f"{pdu.device_name} Output {outlet}"
        icon = ""

        super().__init__(pdu, config_entry, name, icon, enabled_default)

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this output."""
        return "_".join(
            [
                DOMAIN,
                self.pdu.host,
                "outlet",
                str(self.outlet),
            ]
        )

    @property
    def name(self):
        """Return the device's name."""
        return self._name

    @property
    def available(self):
        """Return true if entity is available."""
        return self._available

    @property
    def is_on(self):
        """Return true if the output is turned on."""
        return self._state

    @property
    def device_class(self) -> str | None:
        """Return the device_class."""
        return SwitchDeviceClass.OUTLET

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn switch on."""
        await self.hass.async_add_executor_job(self.pdu.output_on, self.outlet)
        self.schedule_update_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn switch off."""
        await self.hass.async_add_executor_job(self.pdu.output_off, self.outlet)
        self.schedule_update_ha_state()

    async def _pdu_update(self) -> None:
        """Update NetIO PDU entity."""
        self._state = await self.pdu.get_outlet(self.outlet, "State")
        # self._state = tmp.State
