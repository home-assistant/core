"""Platform for sensor integration."""
from __future__ import annotations
from homeassistant.components import oocsi
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from . import oocsiRun


def setup_platform(hass, ConfigEntry, async_add_entities, discovery_info=None):
    """Set up the Oocsi sensor platform."""
    # if discovery_info is None:
    #     return

    async_add_entities(BasicSwitch, True)

    return True


class BasicSwitch(SwitchEntity, oocsiRun):
    def __init__(self) -> None:
        self._Run: oocsiRun
        # super().__init__()

    # @property
    # def icon(self) -> str:
    #     """Return the icon."""
    #     return self._static_info.icon

    # @property
    # def assumed_state(self) -> bool:
    #     """Return true if we do optimistic updates."""

    # def is_on(self) -> bool | None:  # type: ignore[override]
    #     """Return true if the switch is on."""

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self._Run.r._test_oocsi("colorChannel", {"on": True})

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        self._Run._test_oocsi("colorChannel", {"on": False})
        # await self._client.switch_command(self._static_info.key, False)
