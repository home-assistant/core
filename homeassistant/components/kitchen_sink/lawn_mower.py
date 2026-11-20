"""Demo platform that has a couple fake lawn mowers."""

from dataclasses import dataclass
from typing import override

from homeassistant.components.lawn_mower import (
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityEntityDescription,
    LawnMowerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType


@dataclass(frozen=True, kw_only=True)
class DemoLawnMowerEntityDescription(LawnMowerEntityEntityDescription):
    """Describes a demo lawn mower."""

    activity: LawnMowerActivity
    features: LawnMowerEntityFeature


LAWN_MOWERS = (
    DemoLawnMowerEntityDescription(
        key="kitchen_sink_mower_001",
        name="Mower can mow",
        activity=LawnMowerActivity.DOCKED,
        features=LawnMowerEntityFeature.START_MOWING,
    ),
    DemoLawnMowerEntityDescription(
        key="kitchen_sink_mower_002",
        name="Mower can return",
        activity=LawnMowerActivity.RETURNING,
        features=LawnMowerEntityFeature.DOCK
        | LawnMowerEntityFeature.PAUSE
        | LawnMowerEntityFeature.START_MOWING,
    ),
    DemoLawnMowerEntityDescription(
        key="kitchen_sink_mower_003",
        name="Mower can dock",
        activity=LawnMowerActivity.MOWING,
        features=LawnMowerEntityFeature.DOCK | LawnMowerEntityFeature.START_MOWING,
    ),
    DemoLawnMowerEntityDescription(
        key="kitchen_sink_mower_004",
        name="Mower can pause",
        activity=LawnMowerActivity.DOCKED,
        features=LawnMowerEntityFeature.PAUSE | LawnMowerEntityFeature.START_MOWING,
    ),
    DemoLawnMowerEntityDescription(
        key="kitchen_sink_mower_005",
        name="Mower can do all",
        activity=LawnMowerActivity.DOCKED,
        features=LawnMowerEntityFeature.DOCK
        | LawnMowerEntityFeature.PAUSE
        | LawnMowerEntityFeature.START_MOWING
        | LawnMowerEntityFeature.STOP,
    ),
    DemoLawnMowerEntityDescription(
        key="kitchen_sink_mower_006",
        name="Mower is paused",
        activity=LawnMowerActivity.PAUSED,
        features=LawnMowerEntityFeature.DOCK
        | LawnMowerEntityFeature.PAUSE
        | LawnMowerEntityFeature.START_MOWING,
    ),
    DemoLawnMowerEntityDescription(
        key="kitchen_sink_mower_007",
        name="Mower can stop",
        activity=LawnMowerActivity.MOWING,
        features=LawnMowerEntityFeature.STOP | LawnMowerEntityFeature.START_MOWING,
    ),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Demo lawn mowers."""
    async_add_entities(DemoLawnMower(description) for description in LAWN_MOWERS)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Everything but the Kitchen Sink config entry."""
    await async_setup_platform(hass, {}, async_add_entities)


class DemoLawnMower(LawnMowerEntity):
    """Representation of a Demo lawn mower."""

    entity_description: DemoLawnMowerEntityDescription

    def __init__(self, description: DemoLawnMowerEntityDescription) -> None:
        """Initialize the lawn mower."""
        self.entity_description = description
        self._attr_unique_id = description.key
        self._attr_supported_features = description.features
        self._attr_activity = description.activity

    @override
    async def async_start_mowing(self) -> None:
        """Start mowing."""
        self._attr_activity = LawnMowerActivity.MOWING
        self.async_write_ha_state()

    @override
    async def async_dock(self) -> None:
        """Start docking."""
        self._attr_activity = LawnMowerActivity.DOCKED
        self.async_write_ha_state()

    @override
    async def async_pause(self) -> None:
        """Pause mower."""
        self._attr_activity = LawnMowerActivity.PAUSED
        self.async_write_ha_state()

    @override
    async def async_stop(self) -> None:
        """Stop mower."""
        self._attr_activity = LawnMowerActivity.IDLE
        self.async_write_ha_state()
