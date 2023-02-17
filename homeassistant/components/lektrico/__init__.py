"""The Lektrico Charging Station integration."""
from __future__ import annotations

from datetime import datetime, timedelta

from lektricowifi import ChargerConnectionError, lektricowifi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_FRIENDLY_NAME, CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

# List the platforms that you want to support.
PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SWITCH,
]

PARALLEL_UPDATES = 1
SCAN_INTERVAL = timedelta(seconds=10)
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Lektrico Charging Station from a config entry."""
    session = async_get_clientsession(hass)
    charger = lektricowifi.Charger(
        entry.data[CONF_HOST],
        session=session,
    )

    try:
        coordinator = LektricoDeviceDataUpdateCoordinator(
            charger, hass, entry.data[CONF_FRIENDLY_NAME]
        )
        await coordinator.get_config()

    except ChargerConnectionError as lek_ex:
        raise ConfigEntryNotReady(lek_ex) from lek_ex

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Cleanup
        del hass.data[DOMAIN][entry.entry_id]
        if not hass.data[DOMAIN]:
            del hass.data[DOMAIN]
    return unload_ok


class LektricoDeviceDataUpdateCoordinator(DataUpdateCoordinator):
    """The device class for Lektrico charger."""

    _last_client_refresh = datetime.min
    serial_number: int
    board_revision: str

    def __init__(
        self,
        device: lektricowifi.Charger,
        hass: HomeAssistant,
        friendly_name: str,
    ) -> None:
        """Initialize a Lektrico Device."""
        self.device = device
        self._hass = hass
        self.friendly_name = friendly_name.replace(" ", "_")
        self._name = friendly_name
        self._update_fail_count = 0
        self._info = None
        super().__init__(
            hass, LOGGER, name=f"{DOMAIN}-{self._name}", update_interval=SCAN_INTERVAL
        )

    async def get_config(self) -> None:
        """Get device's config."""
        settings = await self.device.charger_config()
        self.serial_number = settings.serial_number
        self.board_revision = settings.board_revision

    async def _async_update_data(self) -> lektricowifi.Info:
        """Async Update device state."""
        try:
            return await self.device.charger_info()
        except ChargerConnectionError as lek_ex:
            raise UpdateFailed(lek_ex) from lek_ex
