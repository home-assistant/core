"""The Lektrico Charging Station integration."""
from __future__ import annotations

from datetime import datetime, timedelta

from aiohttp import ClientSession
from lektricowifi import Device, DeviceConnectionError, lektricowifi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_FRIENDLY_NAME, CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CHARGERS_PLATFORMS, DOMAIN, LB_DEVICES_PLATFORMS, LOGGER

PARALLEL_UPDATES = 1
SCAN_INTERVAL = timedelta(seconds=10)
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Lektrico Charging Station from a config entry."""
    session = async_get_clientsession(hass)

    try:
        coordinator = await create_coordinator(hass, entry, session)
    except DeviceConnectionError as lek_ex:
        raise ConfigEntryNotReady(lek_ex) from lek_ex

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    if coordinator.device_type in (Device.TYPE_1P7K, Device.TYPE_3P22K):
        await hass.config_entries.async_forward_entry_setups(entry, CHARGERS_PLATFORMS)
    elif coordinator.device_type == Device.TYPE_M2W:
        await hass.config_entries.async_forward_entry_setups(
            entry, LB_DEVICES_PLATFORMS
        )
    else:
        # unknown type of device
        raise ConfigEntryError("Unsupported Lektrico device.")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, get_platforms(hass, entry)
    ):
        # Cleanup
        del hass.data[DOMAIN][entry.entry_id]
        if not hass.data[DOMAIN]:
            del hass.data[DOMAIN]
    return unload_ok


async def create_coordinator(
    hass: HomeAssistant, entry: ConfigEntry, session: ClientSession
) -> LektricoDeviceDataUpdateCoordinator:
    """Create the coordinator for Lektrico Charging Station device."""
    coordinator = LektricoDeviceDataUpdateCoordinator(
        hass, entry.data[CONF_FRIENDLY_NAME], entry.data[CONF_HOST], session
    )
    await coordinator.get_config()
    return coordinator


def get_platforms(hass: HomeAssistant, entry: ConfigEntry) -> list[Platform]:
    """Return the platforms for this type of device."""
    _device_type: str = hass.data[DOMAIN][entry.entry_id].device_type
    if _device_type in (Device.TYPE_1P7K, Device.TYPE_3P22K):
        return CHARGERS_PLATFORMS
    return LB_DEVICES_PLATFORMS


class LektricoDeviceDataUpdateCoordinator(DataUpdateCoordinator):
    """The device class for Lektrico device."""

    _last_client_refresh = datetime.min
    serial_number: int
    board_revision: str
    device_type: str

    def __init__(
        self,
        hass: HomeAssistant,
        friendly_name: str,
        host: str,
        session: ClientSession,
    ) -> None:
        """Initialize a Lektrico Device."""
        self.device = lektricowifi.Device(
            host,
            session=session,
        )
        self._hass = hass
        self.friendly_name = friendly_name.replace(" ", "_")
        self._name = friendly_name
        self._update_fail_count = 0
        self._info = None
        super().__init__(
            hass, LOGGER, name=f"{DOMAIN}-{self._name}", update_interval=SCAN_INTERVAL
        )

    async def get_config(self) -> None:
        """Get device's config. This is only asked once."""
        settings = await self.device.device_config()
        self.serial_number = settings.serial_number
        self.board_revision = settings.board_revision
        self.device_type = settings.type

    async def _async_update_data(self) -> lektricowifi.Info:
        """Async Update device state."""
        try:
            info = await self.device.device_info(self.device_type)
            return info
        except DeviceConnectionError as lek_ex:
            raise UpdateFailed(lek_ex) from lek_ex
