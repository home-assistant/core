"""Coordinator for HAVEN local API polling."""

from dataclasses import dataclass
from typing import override

from haveniaq import (
    Capability,
    DeviceInfo,
    HavenApiError,
    HavenClient,
    HavenUnsupportedApiVersionError,
    HavenUnsupportedProductError,
    SensorData,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, LOGGER

type HavenConfigEntry = ConfigEntry[HavenDataUpdateCoordinator]


@dataclass(frozen=True, slots=True)
class HavenCoordinatorData:
    """Data returned by one coordinated device update."""

    sensors: SensorData


class HavenDataUpdateCoordinator(DataUpdateCoordinator[HavenCoordinatorData]):
    """Coordinate sequential polling of a HAVEN device."""

    def __init__(
        self, hass: HomeAssistant, entry: HavenConfigEntry, client: HavenClient
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            name=f"{DOMAIN}_{client.host}",
            update_interval=DEFAULT_SCAN_INTERVAL,
            config_entry=entry,
        )
        self.client = client
        self.info: DeviceInfo

    @override
    async def _async_setup(self) -> None:
        """Fetch stable device metadata before the first poll."""
        try:
            self.info = await self.client.get_info()
        except HavenUnsupportedApiVersionError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="unsupported_api_version",
            ) from err
        except HavenUnsupportedProductError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="unsupported_product",
            ) from err
        except HavenApiError as err:
            raise _update_failed(err) from err

        if not self.info.supports(Capability.AIR_QUALITY):
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="unsupported_product",
            )

    @override
    async def _async_update_data(self) -> HavenCoordinatorData:
        try:
            sensors = await self.client.get_sensors()
        except HavenApiError as err:
            raise _update_failed(err) from err

        return HavenCoordinatorData(sensors=sensors)


def _update_failed(err: HavenApiError) -> UpdateFailed:
    """Create a translated coordinator update error."""
    return UpdateFailed(
        translation_domain=DOMAIN,
        translation_key="update_error",
        translation_placeholders={"error": str(err)},
    )
