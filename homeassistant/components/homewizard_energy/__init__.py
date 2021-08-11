"""The HomeWizard Energy integration."""
from __future__ import annotations
from homeassistant.const import (
    ATTR_ID,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_STATE,
    ATTR_SW_VERSION,
    CONF_NAME,
    CONF_UNIQUE_ID,
)
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from aiohwenergy import HomeWizardEnergy
from .helpers import async_validate_connection
import async_timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    ATTR_API_VERSION,
    ATTR_DATA,
    ATTR_BRIGHTNESS,
    ATTR_POWER_ON,
    ATTR_SWITCHLOCK,
    CONF_API,
    CONF_COORDINATOR,
    DOMAIN,
    MODEL_P1,
    LOGGER,
    PLATFORMS,
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HomeWizard Energy from a config entry."""

    # Get API
    api = HomeWizardEnergy(entry.data.get("host"))
    hass.data[DOMAIN][entry.data[CONF_UNIQUE_ID]][CONF_API] = api

    # Validate connection with device
    if not await async_validate_connection(api):
        return False

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    coordinator = hass.data[DOMAIN][entry.data[CONF_UNIQUE_ID]][
        CONF_COORDINATOR
    ] = HWEUpdateCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.data[CONF_UNIQUE_ID]][CONF_API] = api
    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class HWEUpdateCoordinator(DataUpdateCoordinator):
    """Gather data for the device"""

    def __init__(
        self,
        hass: HomeAssistant,
        api: HomeWizardEnergy,
    ) -> None:
        self.api = api

        update_interval = self.get_update_interval()
        super().__init__(hass, LOGGER, name="", update_interval=update_interval)

    def get_update_interval(self) -> timedelta:
        """Returns 'best' timedelta for a device"""

        delta_default = timedelta(seconds=5)

        try:
            product_type = self.api.device.product_type
        except (NameError, AttributeError):
            return delta_default

        # Check if device is P1 meter with DSMR5.0
        if product_type == MODEL_P1:
            try:
                smr_version = self.api.data.smr_version
                if smr_version == 50:
                    return timedelta(seconds=1)
            except AttributeError:
                pass

        return delta_default

    async def _async_update_data(self) -> dict:
        """Fetch all device and sensor data from api."""
        try:
            async with async_timeout.timeout(10):
                # Update all properties
                status = await self.api.update()

                if not status:
                    raise Exception("Failed to fetch data")

                data = {
                    ATTR_NAME: self.api.device.product_name,
                    ATTR_MODEL: self.api.device.product_type,
                    ATTR_ID: self.api.device.serial,
                    ATTR_SW_VERSION: self.api.device.firmware_version,
                    ATTR_API_VERSION: self.api.device.api_version,
                    ATTR_DATA: {},
                    ATTR_STATE: None,
                }

                for datapoint in self.api.data.available_datapoints:
                    data[ATTR_DATA][datapoint] = getattr(self.api.data, datapoint)

                if self.api.state is not None:
                    data[ATTR_STATE] = {
                        ATTR_POWER_ON: self.api.state.power_on,
                        ATTR_SWITCHLOCK: self.api.state.switch_lock,
                        ATTR_BRIGHTNESS: self.api.state.brightness,
                    }

        except Exception as ex:
            raise UpdateFailed(ex) from ex

        self.name = data[CONF_NAME]
        return data
