"""Provide a mock fan platform.

Call init before using it in your tests to ensure clean test data.
"""
from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from tests.common import MockEntity

ENTITIES = {}


def init(empty=False):
    """Initialize the platform with entities."""
    global ENTITIES

    ENTITIES = (
        {}
        if empty
        else {
            "support_preset_mode": MockFan(
                name="Support fan with preset_mode support",
                supported_features=FanEntityFeature.PRESET_MODE,
                unique_id="unique_support_preset_mode",
                preset_modes=["auto", "eco"],
            )
        }
    )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities_callback: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
):
    """Return mock entities."""
    async_add_entities_callback(list(ENTITIES.values()))


class MockFan(MockEntity, FanEntity):
    """Mock Fan class."""

    @property
    def preset_mode(self) -> str | None:
        """Return preset mode."""
        return self._handle("preset_mode")

    @property
    def preset_modes(self) -> list[str] | None:
        """Return preset mode."""
        return self._handle("preset_modes")

    @property
    def supported_features(self):
        """Return the class of this fan."""
        return self._handle("supported_features")

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        self._attr_preset_mode = preset_mode
        await self.async_update_ha_state()
