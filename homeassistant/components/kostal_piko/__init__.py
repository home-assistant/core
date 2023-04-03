"""Kostal Piko custom component."""
from datetime import timedelta
import logging
from math import ceil

from kostal import InfoVersions, Piko, SettingsGeneral

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]
DEVICE_INFO_IDS = [
    SettingsGeneral.INVERTER_NAME,
    SettingsGeneral.INVERTER_MAKE,
    InfoVersions.SERIAL_NUMBER,
    InfoVersions.ARTICLE_NUMBER,
    InfoVersions.VERSION_FW,
    InfoVersions.VERSION_HW,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Kostal Piko from a config entry."""
    host = entry.data[CONF_HOST]
    user = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    try:
        piko = Piko(async_get_clientsession(hass), host, user, password)
    except Exception as err:
        raise ConfigEntryNotReady from err

    coordinator = PikoUpdateCoordinator(hass, piko)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Kostal Piko from a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
    return unload_ok


class PikoUpdateCoordinator(DataUpdateCoordinator):
    """Get the latest data from the Kostal Piko Inverter."""

    def __init__(
        self, hass: HomeAssistant, piko: Piko, update_interval=timedelta(seconds=15)
    ) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self.piko: Piko = piko
        self._fetch: list[int] = []

        super().__init__(
            self.hass, _LOGGER, name=DOMAIN, update_interval=update_interval
        )

    def start_fetch_data(self, dxs_id: int) -> None:
        """Add the given dxs_id to the data that is being fetched."""
        if dxs_id not in self._fetch:
            self._fetch.append(dxs_id)

    def stop_fetch_data(self, dxs_id: int) -> None:
        """Remove the given dxs_id from the data that is being fetched."""
        if dxs_id in self._fetch:
            self._fetch.remove(dxs_id)

    async def _async_update_data(self) -> dict[int, str]:
        """Fetch data from API endpoint."""
        to_fetch = []
        to_fetch.extend(self._fetch)
        to_fetch.extend(DEVICE_INFO_IDS)

        # The piko api apparently has an artificial limit of
        # a maximum of 12 ids that can be request at a time.
        # So we do multiple requests of 10.
        segments_count = ceil(len(to_fetch) / 10)
        return_data = {}
        exception_count = 0
        for i in range(0, segments_count):
            fetch_segment = to_fetch[10 * i : 10 * (i + 1)]
            try:
                fetched = await self.piko.fetch_props(*fetch_segment)

                for dxs_id in fetch_segment:
                    dxs_entry = fetched.get_entry_by_id(dxs_id)
                    if dxs_entry is not None:
                        return_data[dxs_id] = dxs_entry.value
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.warning(
                    "Fetching of segment %i failed, increasing exception count. Error message: %s",
                    i,
                    err,
                    exc_info=True,
                )
                exception_count += 1

        if len(return_data) == 0 and exception_count > 0:
            raise UpdateFailed()

        return return_data
