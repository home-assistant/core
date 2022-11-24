"""Support for the NextDNS service."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic

from nextdns import Settings

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CoordinatorDataT, NextDnsSettingsUpdateCoordinator
from .const import ATTR_SETTINGS, DOMAIN

PARALLEL_UPDATES = 1

LOCATION_MAP = {
    "switzerland": "ch",
    "european_union": "eu",
    "great_britain": "gb",
    "united_states": "us",
}
INVERTED_LOCATION_MAP = {v: k for k, v in LOCATION_MAP.items()}

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
INVERTED_RETENTION_MAP = {v: k for k, v in RETENTION_MAP.items()}


@dataclass
class NextDnsSelectRequiredKeysMixin(Generic[CoordinatorDataT]):
    """Class for NextDNS entity required keys."""

    state: Callable[[CoordinatorDataT], str]
    select_option_method: str
    option_map: dict[str, Any]


@dataclass
class NextDnsSelectEntityDescription(
    SelectEntityDescription, NextDnsSelectRequiredKeysMixin[CoordinatorDataT]
):
    """NextDNS select entity description."""


SELECTS = [
    NextDnsSelectEntityDescription[Settings](
        key="logs_location",
        name="Logs location",
        entity_category=EntityCategory.CONFIG,
        option_map=LOCATION_MAP,
        state=lambda data: INVERTED_LOCATION_MAP[data.logs_location],
        select_option_method="set_logs_location",
        options=["switzerland", "european_union", "great_britain", "united_states"],
        device_class=f"{DOMAIN}__logs_location",
    ),
    NextDnsSelectEntityDescription[Settings](
        key="logs_retention",
        name="Logs retention",
        entity_category=EntityCategory.CONFIG,
        option_map=RETENTION_MAP,
        state=lambda data: INVERTED_RETENTION_MAP[data.logs_retention],
        select_option_method="set_logs_retention",
        options=[
            "one_hour",
            "six_hours",
            "one_day",
            "one_week",
            "one_month",
            "three_months",
            "six_months",
            "one_year",
            "two_years",
        ],
        device_class=f"{DOMAIN}__logs_retention",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add NextDNS entities from a config_entry."""
    coordinator: NextDnsSettingsUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        ATTR_SETTINGS
    ]

    selects: list[NextDnsSelect] = []
    for description in SELECTS:
        selects.append(NextDnsSelect(coordinator, description))

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
        assert description.options is not None
        self._attr_options = description.options
        self._attr_current_option = description.state(coordinator.data)
        self.entity_description: NextDnsSelectEntityDescription = description

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_current_option = self.entity_description.state(self.coordinator.data)
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        method = getattr(
            self.coordinator.nextdns, self.entity_description.select_option_method
        )
        await method(
            self.coordinator.profile_id, self.entity_description.option_map[option]
        )
