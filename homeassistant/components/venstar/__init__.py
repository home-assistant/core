"""The venstar component."""
import asyncio
from datetime import timedelta

from requests import RequestException
from venstarcolortouch import VenstarColorTouch

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PIN,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import update_coordinator
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import _LOGGER, DOMAIN, VENSTAR_TIMEOUT

PLATFORMS = ["binary_sensor", "climate", "sensor"]


async def async_setup_entry(hass, config):
    """Set up the Venstar thermostat."""
    username = config.data.get(CONF_USERNAME)
    password = config.data.get(CONF_PASSWORD)
    pin = config.data.get(CONF_PIN)
    host = config.data[CONF_HOST]
    timeout = VENSTAR_TIMEOUT
    protocol = "https" if config.data[CONF_SSL] else "http"

    client = VenstarColorTouch(
        addr=host,
        timeout=timeout,
        user=username,
        password=password,
        pin=pin,
        proto=protocol,
    )

    venstar_data_coordinator = VenstarDataUpdateCoordinator(
        hass,
        venstar_connection=client,
    )
    await venstar_data_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[config.entry_id] = venstar_data_coordinator
    hass.config_entries.async_setup_platforms(config, PLATFORMS)

    return True


async def async_unload_entry(hass, config):
    """Unload the config config and platforms."""
    unload_ok = await hass.config_entries.async_unload_platforms(config, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(config.entry_id)
    return unload_ok


class VenstarDataUpdateCoordinator(update_coordinator.DataUpdateCoordinator):
    """Class to manage fetching Venstar data."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        venstar_connection: VenstarColorTouch,
    ) -> None:
        """Initialize global Venstar data updater."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
        )
        self.client = venstar_connection

    async def _async_update_data(self) -> None:
        """Update the state."""
        try:
            await self.hass.async_add_executor_job(self.client.update_info)
        except (OSError, RequestException) as ex:
            raise update_coordinator.UpdateFailed(
                f"Exception during Venstar info update: {ex}"
            ) from ex

        # older venstars sometimes cannot handle rapid sequential connections
        await asyncio.sleep(1)

        try:
            await self.hass.async_add_executor_job(self.client.update_sensors)
        except (OSError, RequestException) as ex:
            raise update_coordinator.UpdateFailed(
                f"Exception during Venstar sensor update: {ex}"
            ) from ex

        # older venstars sometimes cannot handle rapid sequential connections
        await asyncio.sleep(1)

        try:
            await self.hass.async_add_executor_job(self.client.update_alerts)
        except (OSError, RequestException) as ex:
            raise update_coordinator.UpdateFailed(
                f"Exception during Venstar alert update: {ex}"
            ) from ex
        return None


class VenstarEntity(CoordinatorEntity):
    """Representation of a Venstar entity."""

    coordinator: VenstarDataUpdateCoordinator

    def __init__(
        self,
        venstar_data_coordinator: VenstarDataUpdateCoordinator,
        config: ConfigEntry,
    ) -> None:
        """Initialize the data object."""
        super().__init__(venstar_data_coordinator)
        self._config = config
        self._client = venstar_data_coordinator.client

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    @property
    def device_info(self):
        """Return the device information for this entity."""
        return {
            "identifiers": {(DOMAIN, self._config.entry_id)},
            "name": self._client.name,
            "manufacturer": "Venstar",
            "model": f"{self._client.model}-{self._client.get_type()}",
            "sw_version": self._client.get_api_ver(),
        }
