"""DataUpdateCoordinator for the nina integration."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import re
from typing import Any

from pynina import ApiError, Nina

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import _LOGGER, DOMAIN, SCAN_INTERVAL


@dataclass
class NinaWarningData:
    """Class to hold the warning data."""

    id: str
    headline: str
    description: str
    sender: str
    severity: str
    recommended_actions: str
    affected_areas: str
    sent: str
    start: str
    expires: str
    is_valid: bool


class NINADataUpdateCoordinator(
    DataUpdateCoordinator[dict[str, list[NinaWarningData]]]
):
    """Class to manage fetching NINA data API."""

    def __init__(
        self,
        hass: HomeAssistant,
        regions: dict[str, str],
        headline_filter: str,
        area_filter: str,
    ) -> None:
        """Initialize."""
        self._regions: dict[str, str] = regions
        self._nina: Nina = Nina(async_get_clientsession(hass))
        self.headline_filter: str = headline_filter
        self.area_filter: str = area_filter

        for region in regions:
            self._nina.addRegion(region)

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

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

                warning_data: NinaWarningData = NinaWarningData(
                    raw_warn.id,
                    raw_warn.headline,
                    raw_warn.description,
                    raw_warn.sender,
                    raw_warn.severity,
                    " ".join([str(action) for action in raw_warn.recommended_actions]),
                    affected_areas_string,
                    raw_warn.sent or "",
                    raw_warn.start or "",
                    raw_warn.expires or "",
                    raw_warn.isValid(),
                )
                warnings_for_regions.append(warning_data)

            return_data[region_id] = warnings_for_regions

        return return_data
