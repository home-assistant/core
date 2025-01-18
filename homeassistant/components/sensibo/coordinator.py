"""DataUpdateCoordinator for the Sensibo integration."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from pysensibo import SensiboClient
from pysensibo.exceptions import AuthenticationError, SensiboError
from pysensibo.model import SensiboData

from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER, TIMEOUT

if TYPE_CHECKING:
    from . import SensiboConfigEntry

REQUEST_REFRESH_DELAY = 0.35


class SensiboDataUpdateCoordinator(DataUpdateCoordinator[SensiboData]):
    """A Sensibo Data Update Coordinator."""

    config_entry: SensiboConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: SensiboConfigEntry) -> None:
        """Initialize the Sensibo coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            # We don't want an immediate refresh since the device
            # takes a moment to reflect the state change
            request_refresh_debouncer=Debouncer(
                hass, LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=False
            ),
        )
        self.client = SensiboClient(
            self.config_entry.data[CONF_API_KEY],
            session=async_get_clientsession(hass),
            timeout=TIMEOUT,
        )
        self.previous_devices: set[str] = set()

    def get_devices(
        self, added_devices: set[str]
    ) -> tuple[set[str], set[str], set[str]]:
        """Addition and removal of devices."""
        data = self.data
        motion_sensors = {
            sensor_id
            for device_data in data.parsed.values()
            if device_data.motion_sensors
            for sensor_id in device_data.motion_sensors
        }
        devices: set[str] = set(data.parsed)
        new_devices: set[str] = motion_sensors | devices - added_devices
        remove_devices = added_devices - devices - motion_sensors
        added_devices = (added_devices - remove_devices) | new_devices

        return (new_devices, remove_devices, added_devices)

    async def _async_update_data(self) -> SensiboData:
        """Fetch data from Sensibo."""
        try:
            data = await self.client.async_get_devices_data()
        except AuthenticationError as error:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_error",
            ) from error
        except SensiboError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(error)},
            ) from error

        if not data.raw:
            raise UpdateFailed(translation_domain=DOMAIN, translation_key="no_data")

        current_devices = set(data.parsed)
        for device_data in data.parsed.values():
            if device_data.motion_sensors:
                for motion_sensor_id in device_data.motion_sensors:
                    current_devices.add(motion_sensor_id)

        if stale_devices := self.previous_devices - current_devices:
            LOGGER.debug("Removing stale devices: %s", stale_devices)
            device_registry = dr.async_get(self.hass)
            for _id in stale_devices:
                device = device_registry.async_get_device(identifiers={(DOMAIN, _id)})
                if device:
                    device_registry.async_update_device(
                        device_id=device.id,
                        remove_config_entry_id=self.config_entry.entry_id,
                    )
        self.previous_devices = current_devices

        return data
