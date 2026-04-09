"""Cover group."""

from __future__ import annotations  # noqa: D100, EXE002

from functools import cached_property
import logging

from homeassistant.components.cover import (
    DEVICE_CLASSES as COVER_DEVICE_CLASSES,
    CoverDeviceClass,
)
from homeassistant.components.group.cover import CoverGroup
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .auto_area import AutoArea
from .const import COVER_GROUP_ENTITY_PREFIX, COVER_GROUP_PREFIX

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entities."""
    areas = area_registry.async_get(hass)

    # Loop over each area and find associated motion sensors
    for area_id, area in areas.areas.items():
        auto_area = AutoArea(hass=hass, areaid=area_id)

        cover_entity_ids: list[str] = auto_area.get_area_entity_ids(
            COVER_DEVICE_CLASSES
        )

        if not cover_entity_ids:
            _LOGGER.info(
                "%s: No covers found in area. Not creating cover group.",
                auto_area.area_name,
            )
        else:
            async_add_entities(
                [AutoCoverGroup(hass, auto_area, entity_ids=cover_entity_ids)]
            )


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the platform."""
    # We only want this platform to be set up via discovery.
    if discovery_info is None:
        return

    areas = area_registry.async_get(hass)

    # Loop over each area and find associated motion sensors
    for area_id, area in areas.areas.items():
        auto_area = AutoArea(hass=hass, areaid=area_id)

        cover_entity_ids: list[str] = auto_area.get_area_entity_ids(
            COVER_DEVICE_CLASSES
        )

        if not cover_entity_ids:
            _LOGGER.info(
                "%s: No covers found in area. Not creating cover group.",
                auto_area.area_name,
            )
        else:
            add_entities([AutoCoverGroup(hass, auto_area, entity_ids=cover_entity_ids)])


class AutoCoverGroup(CoverGroup):
    """Cover group with area covers."""

    def __init__(self, hass, auto_area: AutoArea, entity_ids: list[str]) -> None:
        """Initialize cover group."""
        self.hass = hass
        self.auto_area = auto_area
        self._device_class = CoverDeviceClass.BLIND
        self._name_prefix = COVER_GROUP_PREFIX
        self._prefix = COVER_GROUP_ENTITY_PREFIX
        self.entity_ids: list[str] = entity_ids

        CoverGroup.__init__(
            self,
            entities=self.entity_ids,
            name=None,
            unique_id=self._attr_unique_id,
        )
        _LOGGER.info(
            "%s (%s): Initialized cover group. Entities: %s",
            self.auto_area.area_name,
            self.device_class,
            self.entity_ids,
        )

    @cached_property
    def name(self):
        """Name of this entity."""
        return f"{self._name_prefix}{self.auto_area.area_name}"

    @cached_property
    def device_info(self) -> DeviceInfo:
        """Information about this device."""
        return self.auto_area.device_info

    @cached_property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return f"{self.auto_area.area_id}_cover_group"

    @property
    def icon(self):
        # Return the specified icon or a default one
        return "mdi:garage-variant"
