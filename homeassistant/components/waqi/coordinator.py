"""Coordinator for the World Air Quality Index (WAQI) integration."""

from datetime import timedelta
from typing import override

from aiowaqi import (
    WAQIAirQuality,
    WAQIAuthenticationError,
    WAQIClient,
    WAQIError,
    WAQIUnknownStationError,
)

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_STATION_NUMBER, DOMAIN, LOGGER

type WAQIConfigEntry = ConfigEntry[dict[str, WAQIDataUpdateCoordinator]]


class WAQIDataUpdateCoordinator(DataUpdateCoordinator[WAQIAirQuality]):
    """The WAQI Data Update Coordinator."""

    config_entry: WAQIConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: WAQIConfigEntry,
        subentry: ConfigSubentry,
        client: WAQIClient,
    ) -> None:
        """Initialize the WAQI data coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=subentry.title,
            update_interval=timedelta(minutes=5),
        )
        self._client = client
        self.subentry = subentry

    @override
    async def _async_update_data(self) -> WAQIAirQuality:
        issue_id = f"station_not_found_{self.subentry.subentry_id}"
        try:
            air_quality = await self._client.get_by_station_number(
                self.subentry.data[CONF_STATION_NUMBER]
            )
        except WAQIAuthenticationError as exc:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_api_key",
            ) from exc
        except WAQIUnknownStationError as exc:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                config_entry_id=self.config_entry.entry_id,
                is_fixable=True,
                severity=ir.IssueSeverity.ERROR,
                translation_key="station_not_found",
                translation_placeholders={"name": self.subentry.title},
                data={
                    "entry_id": self.config_entry.entry_id,
                    "subentry_id": self.subentry.subentry_id,
                    "name": self.subentry.title,
                },
            )
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="station_not_found",
                translation_placeholders={"name": self.subentry.title},
            ) from exc
        except WAQIError as exc:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"error": str(exc)},
            ) from exc
        ir.async_delete_issue(self.hass, DOMAIN, issue_id)
        return air_quality
