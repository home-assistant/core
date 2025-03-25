from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.components.sensor import SensorEntity
import logging
import aiohttp
from datetime import timedelta

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the component."""
    return True


async def async_setup_entry(hass, entry):
    """Set up a sensor from a config entry."""

    # Fetch the configuration data from the entry
    name = entry.data.get("name", "TheSilentWaveSensor")
    host = entry.data.get("host", "")
    scan_interval = entry.data.get("scan_interval", 10)
    url = f"http://{host}:8080/api/status"

    # Define your update coordinator for polling API
    class TheSilentWaveCoordinator(DataUpdateCoordinator):
        """Class to manage fetching the data from the API."""

        def __init__(self, hass, name, url, scan_interval):
            """Initialize the coordinator."""
            self._name = name
            self._url = url
            super().__init__(
                hass,
                _LOGGER,
                name=name,
                update_interval=timedelta(seconds=scan_interval),
            )

        async def _async_update_data(self):
            """Fetch data from the API."""
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.get(self._url) as response:
                        response.raise_for_status()
                        data = await response.text()
                        # Convert "1" to "on" and "0" to "off"
                        return "on" if data.strip() == "1" else "off"
                except aiohttp.ClientError as err:
                    raise UpdateFailed(f"Error fetching data from API: {err}")

    # Create the coordinator with scan_interval
    coordinator = TheSilentWaveCoordinator(hass, name, url, scan_interval)
    await coordinator.async_config_entry_first_refresh()

    # Register the sensor entity
    hass.data.setdefault("thesilentwave", {})
    hass.data["thesilentwave"][entry.entry_id] = coordinator

    # Add the sensor entity to Home Assistant
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    return True
