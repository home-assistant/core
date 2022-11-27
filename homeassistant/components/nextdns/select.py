"""Support for the NextDNS service."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic

from aiohttp import ClientError
from aiohttp.client_exceptions import ClientConnectorError
from nextdns import ApiError, Settings

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CoordinatorDataT, NextDnsSettingsUpdateCoordinator
from .const import ATTR_SETTINGS, DOMAIN

PARALLEL_UPDATES = 1


RETENTION_MAP = {
    "one_hour": 1,
    "six_hours": 6,
    "one_day": 24,
    "one_week": 168,
    "one_month": 720,
    "three_months": 2160,
    "six_months": 4320,
    "one_year": 8760,
    "two_years": 17520,
}
RETENTION_INVERTED_MAP = {v: k for k, v in RETENTION_MAP.items()}


@dataclass
class NextDnsSelectRequiredKeysMixin(Generic[CoordinatorDataT]):
    """Class for NextDNS entity required keys."""

    current_option: Callable[[CoordinatorDataT], str]
    select_option_method: str
    option_map: dict[str, Any]


@dataclass
class NextDnsSelectEntityDescription(
    SelectEntityDescription, NextDnsSelectRequiredKeysMixin[CoordinatorDataT]
):
    """NextDNS select entity description."""


LOGS_RETENTION_SELECT = NextDnsSelectEntityDescription[Settings](
    key="logs_retention",
    name="Logs retention",
    entity_category=EntityCategory.CONFIG,
    icon="mdi:history",
    option_map=RETENTION_MAP,
    current_option=lambda data: RETENTION_INVERTED_MAP[data.logs_retention],
    select_option_method="set_logs_retention",
    device_class=f"{DOMAIN}__logs_retention",
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add NextDNS entities from a config_entry."""
    coordinator: NextDnsSettingsUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        ATTR_SETTINGS
    ]

    selects: list[NextDnsSelect] = []
    selects.append(NextDnsSelect(coordinator, LOGS_RETENTION_SELECT))

    async_add_entities(selects)


class NextDnsSelect(CoordinatorEntity[NextDnsSettingsUpdateCoordinator], SelectEntity):
    """Define a NextDNS select."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NextDnsSettingsUpdateCoordinator,
        description: NextDnsSelectEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.profile_id}_{description.key}"
        self._attr_options = list(description.option_map.keys())
        self._attr_current_option = description.current_option(coordinator.data)
        self.entity_description: NextDnsSelectEntityDescription = description
        self._select_option = getattr(
            self.coordinator.nextdns, self.entity_description.select_option_method
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_current_option = self.entity_description.current_option(
            self.coordinator.data
        )
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        try:
            result = await self._select_option(
                self.coordinator.profile_id, self.entity_description.option_map[option]
            )
        except (
            ApiError,
            ClientConnectorError,
            asyncio.TimeoutError,
            ClientError,
            ValueError,
        ) as err:
            raise HomeAssistantError(
                f"NextDNS API returned an error calling set_setting for {self.entity_id}: {err}"
            ) from err

        if result:
            self._attr_current_option = option
            self.async_write_ha_state()
