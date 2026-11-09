"""Data update coordinator for the FENIX Control integration."""

from dataclasses import dataclass, replace
from typing import override

from pyfenixcontrol import (
    Device,
    FenixControlAuthError,
    FenixControlClient,
    FenixControlError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_INTERVAL

type FenixControlConfigEntry = ConfigEntry[FenixControlCoordinator]


@dataclass
class FenixControlData:
    """State of all thermostats of the account."""

    devices: dict[str, Device]


class FenixControlCoordinator(DataUpdateCoordinator[FenixControlData]):
    """Poll the state of all thermostats of the account."""

    config_entry: FenixControlConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: FenixControlConfigEntry,
        client: FenixControlClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        # Thermostats commanded while a poll runs; its snapshot may predate the
        # command and must not overwrite the commanded state
        self._commanded: set[str] = set()

    @override
    async def _async_update_data(self) -> FenixControlData:
        """Fetch the state of all thermostats."""
        self._commanded.clear()
        try:
            installations = await self.client.get_installations()
            for installation in installations:
                await self._trigger_installation_update(installation.id)
            # Read the devices last so the snapshot is as fresh as possible
            devices = await self.client.get_devices(installations)
        except FenixControlAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="auth_failed"
            ) from err
        except FenixControlError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="update_failed"
            ) from err

        fresh = {device.id: device for device in devices}
        for device_id in self._commanded & fresh.keys():
            fresh[device_id] = self.data.devices[device_id]
        return FenixControlData(devices=fresh)

    def async_set_device(self, device: Device) -> None:
        """Show the commanded state of a thermostat until a later poll."""
        self._commanded.add(device.id)
        self.data = replace(self.data, devices={**self.data.devices, device.id: device})
        # Keep the poll schedule; frequent commands must not postpone polling
        self.async_update_listeners()

    async def _trigger_installation_update(self, installation_id: str) -> None:
        """Ask the thermostats of an installation to report fresh values."""
        try:
            await self.client.trigger_installation_update(installation_id)
        except FenixControlAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="auth_failed"
            ) from err
        except FenixControlError as err:
            # Best effort: the cloud often rejects this with a transient 5xx
            LOGGER.debug(
                "Update trigger for installation %s failed: %s", installation_id, err
            )
