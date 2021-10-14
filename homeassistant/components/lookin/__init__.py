"""The lookin integration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .aiolookin import (
    POWER_CMD,
    POWER_OFF_CMD,
    POWER_ON_CMD,
    Climate,
    Device,
    DeviceNotFound,
    LookInHttpProtocol,
    LookinUDPSubscriptions,
    Remote,
    start_lookin_udp,
)
from .const import DOMAIN, LOGGER, PLATFORMS


@dataclass
class LookinData:
    """Data for the lookin integration."""

    lookin_udp_subs: LookinUDPSubscriptions
    lookin_device: Device
    meteo_coordinator: DataUpdateCoordinator
    devices: list[dict[str, Any]]
    lookin_protocol: LookInHttpProtocol


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up lookin from a config entry."""

    host = entry.data[CONF_HOST]
    lookin_protocol = LookInHttpProtocol(
        host=host, session=async_get_clientsession(hass)
    )

    try:
        lookin_device = await lookin_protocol.get_info()
        devices = await lookin_protocol.get_devices()
    except DeviceNotFound as ex:
        raise ConfigEntryNotReady from ex

    meteo_coordinator: DataUpdateCoordinator = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=entry.title,
        update_method=lookin_protocol.get_meteo_sensor,
        update_interval=timedelta(seconds=15),
    )
    await meteo_coordinator.async_config_entry_first_refresh()

    lookin_udp_subs = LookinUDPSubscriptions()
    entry.async_on_unload(await start_lookin_udp(lookin_udp_subs))

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = LookinData(
        lookin_udp_subs=lookin_udp_subs,
        lookin_device=lookin_device,
        meteo_coordinator=meteo_coordinator,
        devices=devices,
        lookin_protocol=lookin_protocol,
    )

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


class LookinEntity(Entity):
    """A base class for lookin entities."""

    def __init__(
        self,
        uuid: str,
        device: Remote | Climate,
        lookin_data: LookinData,
    ) -> None:
        """Init the base entity."""
        self._device = device
        self._uuid = uuid
        self._lookin_device = lookin_data.lookin_device
        self._lookin_protocol = lookin_data.lookin_protocol
        self._lookin_udp_subs = lookin_data.lookin_udp_subs
        self._attr_unique_id = uuid

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._device.name

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the remote."""
        return {
            "identifiers": {(DOMAIN, self._uuid)},
            "name": self._device.name,
            "model": self._device.device_type,
            "via_device": (DOMAIN, self._lookin_device.id),
        }

    @callback
    def _async_push_update(self, msg):
        """Process an update pushed via UDP."""
        import pprint

        pprint.print([self, msg])

    async def async_added_to_hass(self) -> None:
        """Called when the entity is added to hass."""
        self.async_on_remove(
            self._lookin_udp_subs.subscribe(
                self._lookin_device.id, self._async_push_update
            )
        )
        return await super().async_added_to_hass()


class LookinPowerEntity(LookinEntity):
    """A Lookin entity that has a power on and power off command."""

    def __init__(
        self,
        uuid: str,
        device: Remote | Climate,
        lookin_data: LookinData,
    ) -> None:
        """Init the power entity."""
        super().__init__(uuid, device, lookin_data)
        self._power_on_command: str = POWER_CMD
        self._power_off_command: str = POWER_CMD
        function_names = {function.name for function in self._device.functions}
        if POWER_ON_CMD in function_names:
            self._power_on_command = POWER_ON_CMD
        if POWER_OFF_CMD in function_names:
            self._power_off_command = POWER_OFF_CMD
