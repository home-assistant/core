"""The lookin integration."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID, CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
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
    Remote,
)
from .const import (
    DEVICES,
    DOMAIN,
    LOGGER,
    LOOKIN_DEVICE,
    METEO_COORDINATOR,
    PLATFORMS,
    PROTOCOL,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up lookin from a config entry."""

    LOGGER.warning("Lookin service started")
    LOGGER.warning("config_entry.data - <%s>", entry.data)
    LOGGER.warning("Lookin service CONF_DEVICE_ID <%s>", entry.data[CONF_DEVICE_ID])
    LOGGER.warning("Lookin service CONF_HOST <%s>", entry.data[CONF_HOST])
    LOGGER.warning("Lookin service entry.entry_id <%s>", entry.entry_id)

    lookin_protocol = LookInHttpProtocol(
        host=entry.data[CONF_HOST], session=async_get_clientsession(hass)
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

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        CONF_HOST: entry.data[CONF_HOST],
        CONF_DEVICE_ID: entry.data[CONF_DEVICE_ID],
        CONF_NAME: entry.data[CONF_NAME],
        LOOKIN_DEVICE: lookin_device,
        METEO_COORDINATOR: meteo_coordinator,
        DEVICES: devices,
        PROTOCOL: lookin_protocol,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


class LookinEntity(Entity):
    """A base class for lookin entities."""

    def __init__(
        self,
        uuid: str,
        lookin_protocol: LookInHttpProtocol,
        device: Remote | Climate,
        lookin_device: Device,
    ) -> None:
        """Init the base entity."""
        self._device = device
        self._uuid = uuid
        self._lookin_device = lookin_device
        self._lookin_protocol = lookin_protocol
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
            "model": self._device.type,
            "via_device": (DOMAIN, self._lookin_device.id),
        }


class LookinPowerEntity(LookinEntity):
    """A Lookin entity that has a power on and power off command."""

    def __init__(
        self,
        uuid: str,
        lookin_protocol: LookInHttpProtocol,
        device: Remote | Climate,
        lookin_device: Device,
    ) -> None:
        """Init the power entity."""
        super().__init__(uuid, lookin_protocol, device, lookin_device)
        self._power_on_command: str = POWER_CMD
        self._power_off_command: str = POWER_CMD
        function_names = {function.name for function in self._device.functions}
        if POWER_ON_CMD in function_names:
            self._power_on_command = POWER_ON_CMD
        if POWER_OFF_CMD in function_names:
            self._power_off_command = POWER_OFF_CMD
