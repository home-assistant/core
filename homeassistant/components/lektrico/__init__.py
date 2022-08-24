"""The Lektrico Charging Station integration."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging

from lektricowifi import lektricowifi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_FRIENDLY_NAME, CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

# List the platforms that you want to support.
PLATFORMS = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SWITCH,
]

_LOGGER = logging.getLogger(__name__)
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

    settings = await charger.charger_config()
    _lektrico_device = LektricoDeviceDataUpdateCoordinator(
        charger, hass, entry.data[CONF_FRIENDLY_NAME], settings
    )

    await _lektrico_device.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = _lektrico_device
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

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

    def __init__(
        self,
        device: lektricowifi.Charger,
        hass: HomeAssistant,
        friendly_name: str,
        settings: lektricowifi.Settings,
    ) -> None:
        """Initialize a Lektrico Device."""
        self.device = device
        self._hass = hass
        self.friendly_name = friendly_name.replace(" ", "_")
        self.serial_number = settings.serial_number
        self.board_revision = settings.board_revision
        self._name = friendly_name
        self._update_fail_count = 0
        self._info = None
        super().__init__(
            hass, _LOGGER, name=f"{DOMAIN}-{self._name}", update_interval=SCAN_INTERVAL
        )

    async def _async_update_data(self) -> lektricowifi.Info:
        """Async Update device state."""
        a_data = self.device.charger_info()
        data = await a_data
        entity_reg = er.async_get(self._hass)
        my_entry = entity_reg.async_get(f"sensor.{self.friendly_name}_charger_state")
        if my_entry is not None:
            dev_reg = dr.async_get(self._hass)
            if my_entry.device_id is not None:
                device = dev_reg.async_get(my_entry.device_id)
                if device is not None:
                    dev_reg.async_update_device(device.id, sw_version=data.fw_version)
        return data
