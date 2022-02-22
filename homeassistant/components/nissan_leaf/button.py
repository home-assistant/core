"""Button to start charging the Nissan Leaf."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DATA_CHARGING, DATA_LEAF, LeafEntity

_LOGGER = logging.getLogger(__name__)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up of a Nissan Leaf button."""
    if discovery_info is None:
        return

    entities: list[LeafEntity] = []
    for vin, datastore in hass.data[DATA_LEAF].items():
        _LOGGER.debug("Adding button for vin=%s", vin)
        entities.append(LeafChargingButton(datastore))

    add_entities(entities, True)


class LeafChargingButton(LeafEntity, ButtonEntity):
    """Charging Button class."""

    _attr_icon = "mdi:power"

    @property
    def name(self) -> str:
        """Sensor name."""
        return f"Start {self.car.leaf.nickname} Charging"

    @property
    def available(self) -> bool:
        """Button availability."""
        return self.car.data[DATA_CHARGING] is not None

    async def async_press(self) -> None:
        """Start charging."""
        await self.car.async_start_charging()
