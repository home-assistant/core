"""The Niko home control integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from nclib.errors import NetcatError
from nikohomecontrol import NikoHomeControl

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.util import Throttle

PLATFORMS: list[Platform] = [Platform.LIGHT]

type NikoHomeControlConfigEntry = ConfigEntry[NikoHomeControlData]


_LOGGER = logging.getLogger(__name__)
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=1)


async def async_setup_entry(
    hass: HomeAssistant, entry: NikoHomeControlConfigEntry
) -> bool:
    """Set Niko Home Control from a config entry."""
    try:
        controller = NikoHomeControl({"ip": entry.data[CONF_HOST], "port": 8000})
        niko_data = NikoHomeControlData(hass, controller)
        await niko_data.async_update()
    except NetcatError as err:
        raise ConfigEntryNotReady("cannot connect to controller.") from err
    except OSError as err:
        raise ConfigEntryNotReady(
            "unknown error while connecting to controller."
        ) from err

    entry.runtime_data = niko_data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: NikoHomeControlConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


class NikoHomeControlData:
    """The class for handling data retrieval."""

    def __init__(self, hass, nhc):
        """Set up Niko Home Control Data object."""
        self.nhc = nhc
        self.hass = hass
        self.available = True
        self.data = {}
        self._system_info = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the latest data from the NikoHomeControl API."""
        _LOGGER.debug("Fetching async state in bulk")
        try:
            self.data = await self.hass.async_add_executor_job(
                self.nhc.list_actions_raw
            )
            self.available = True
        except OSError as ex:
            _LOGGER.error("Unable to retrieve data from Niko, %s", str(ex))
            self.available = False

    def get_state(self, aid):
        """Find and filter state based on action id."""
        for state in self.data:
            if state["id"] == aid:
                return state["value1"]
        _LOGGER.error("Failed to retrieve state off unknown light")
        return None
