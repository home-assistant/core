"""DataUpdateCoordinator for the Helty Flow Cloud integration."""

import logging
from typing import override

from pyheltycloud import (
    HeltyCloud,
    HeltyCloudAuthError,
    HeltyCloudError,
    HeltyDevice,
    HeltyState,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type HeltyCloudConfigEntry = ConfigEntry[list[HeltyCloudDataUpdateCoordinator]]


class HeltyCloudDataUpdateCoordinator(DataUpdateCoordinator[HeltyState]):
    """Coordinate a single poll of one VMC for all its entities."""

    config_entry: HeltyCloudConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: HeltyCloudConfigEntry,
        client: HeltyCloud,
        device: HeltyDevice,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN} {device.serial_number}",
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self.device = device

    @override
    async def _async_update_data(self) -> HeltyState:
        """Read the last state the panel sent to the cloud.

        The panel holds its own connection to the cloud and reports on any
        significant change as well as on a timer, so reading is enough to
        follow it. Prompting it to report would be a message to the panel
        itself, which the manufacturer asks to keep for the confirmation
        after a command.
        """
        try:
            return await self.client.get_last_telemetry(self.device.serial_number)
        except HeltyCloudAuthError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        except HeltyCloudError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
