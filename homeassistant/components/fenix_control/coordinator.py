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

    @override
    async def _async_update_data(self) -> FenixControlData:
        """Fetch the state of all thermostats."""
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

        # Some thermostats stop reporting their own name; the room keeps it
        room_names = {
            (installation.id, room.id): room.name
            for installation in installations
            for room in installation.rooms
        }
        return FenixControlData(
            devices={
                device.id: device
                if device.name
                else replace(
                    device,
                    name=room_names.get((device.installation_id, device.room_id)),
                )
                for device in devices
            }
        )

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
