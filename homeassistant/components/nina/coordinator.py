"""DataUpdateCoordinator for the nina integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any

from pynina import ApiError, Nina

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    _LOGGER,
    CONF_AREA_FILTER,
    CONF_FILTERS,
    CONF_HEADLINE_FILTER,
    CONF_REGIONS,
    DOMAIN,
    SCAN_INTERVAL,
)

type NinaConfigEntry = ConfigEntry[NINADataUpdateCoordinator]


@dataclass
class NinaWarningData:
    """Class to hold the warning data."""

    id: str
    headline: str
    description: str
    sender: str
    severity: str | None
    recommended_actions: str
    affected_areas_short: str
    affected_areas: str
    more_info_url: str
    sent: datetime
    start: datetime | None
    expires: datetime | None
    is_valid: bool


class NINADataUpdateCoordinator(
    DataUpdateCoordinator[dict[str, list[NinaWarningData]]]
):
    """Class to manage fetching NINA data API."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        self._nina: Nina = Nina(async_get_clientsession(hass))
        self.headline_filter: str = config_entry.data[CONF_FILTERS][
            CONF_HEADLINE_FILTER
        ]
        self.area_filter: str = config_entry.data[CONF_FILTERS][CONF_AREA_FILTER]

        regions: dict[str, str] = config_entry.data[CONF_REGIONS]
        for region in regions:
            self._nina.add_region(region)

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, list[NinaWarningData]]:
        """Update data."""
        async with asyncio.timeout(10):
            try:
                await self._nina.update()
            except ApiError as err:
                raise UpdateFailed(err) from err
            return self._parse_data()

    @staticmethod
    def _remove_duplicate_warnings(
        warnings: dict[str, list[Any]],
    ) -> dict[str, list[Any]]:
        """Remove warnings with the same title and expires timestamp in a region."""
        all_filtered_warnings: dict[str, list[Any]] = {}

        for region_id, raw_warnings in warnings.items():
            filtered_warnings: list[Any] = []
            processed_details: list[tuple[str, str]] = []

            for raw_warn in raw_warnings:
                if (raw_warn.headline, raw_warn.expires) in processed_details:
                    continue

                processed_details.append((raw_warn.headline, raw_warn.expires))

                filtered_warnings.append(raw_warn)

            all_filtered_warnings[region_id] = filtered_warnings

        return all_filtered_warnings

    def _parse_data(self) -> dict[str, list[NinaWarningData]]:
        """Parse warning data."""

        return_data: dict[str, list[NinaWarningData]] = {}

        for region_id, raw_warnings in self._remove_duplicate_warnings(
            self._nina.warnings
        ).items():
            warnings_for_regions: list[NinaWarningData] = []

            for raw_warn in raw_warnings:
                if re.search(
                    self.headline_filter, raw_warn.headline, flags=re.IGNORECASE
                ):
                    _LOGGER.debug(
                        f"Ignore warning ({raw_warn.id}) by headline filter ({self.headline_filter}) with headline: {raw_warn.headline}"
                    )
                    continue

                affected_areas_string: str = ", ".join(
                    [str(area) for area in raw_warn.affected_areas]
                )

                if not re.search(
                    self.area_filter, affected_areas_string, flags=re.IGNORECASE
                ):
                    _LOGGER.debug(
                        f"Ignore warning ({raw_warn.id}) by area filter ({self.area_filter}) with area: {affected_areas_string}"
                    )
                    continue

                shortened_affected_areas: str = (
                    affected_areas_string[0:250] + "..."
                    if len(affected_areas_string) > 250
                    else affected_areas_string
                )

                severity = (
                    None
                    if raw_warn.severity.lower() == "unknown"
                    else raw_warn.severity
                )

                warning_data: NinaWarningData = NinaWarningData(
                    raw_warn.id,
                    raw_warn.headline,
                    raw_warn.description,
                    raw_warn.sender or "",
                    severity,
                    " ".join([str(action) for action in raw_warn.recommended_actions]),
                    shortened_affected_areas,
                    affected_areas_string,
                    raw_warn.web or "",
                    datetime.fromisoformat(raw_warn.sent),
                    datetime.fromisoformat(raw_warn.start) if raw_warn.start else None,
                    datetime.fromisoformat(raw_warn.expires)
                    if raw_warn.expires
                    else None,
                    raw_warn.is_valid,
                )
                warnings_for_regions.append(warning_data)

            return_data[region_id] = warnings_for_regions

        return return_data
