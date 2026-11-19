"""Data update coordinator for the Untappd integration."""

from dataclasses import dataclass
from typing import override

from aiountappd import (
    Checkin,
    UntappdAuthenticationError,
    UntappdClient,
    UntappdError,
    User,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_INTERVAL

type UntappdConfigEntry = ConfigEntry[UntappdDataUpdateCoordinator]


@dataclass(frozen=True, kw_only=True)
class UntappdData:
    """Data of an Untappd account."""

    user: User
    last_checkin: Checkin | None


class UntappdDataUpdateCoordinator(DataUpdateCoordinator[UntappdData]):
    """Fetch the statistics and latest check-in of an Untappd account."""

    config_entry: UntappdConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: UntappdConfigEntry,
        client: UntappdClient,
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
    async def _async_update_data(self) -> UntappdData:
        """Fetch data from Untappd."""
        try:
            user = await self.client.get_user_info()
            checkins = await self.client.get_user_checkins(limit=1)
        except UntappdAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        except UntappdError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        return UntappdData(user=user, last_checkin=checkins[0] if checkins else None)
