from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

import logging

from screenlogicpy.const import ON_OFF

from . import ScreenlogicEntity

from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up entry."""
    entities = []
    for switch in hass.data[DOMAIN][config_entry.unique_id]["devices"]["switch"]:
        _LOGGER.info(switch)
        entities.append(
            ScreenLogicSwitch(
                hass.data[DOMAIN][config_entry.unique_id]["coordinator"], switch
            )
        )
    async_add_entities(entities, True)


class ScreenLogicSwitch(ScreenlogicEntity, SwitchEntity):
    """ScreenLogic switch entitiy."""

    def __init__(self, coordinator, switch):
        super().__init__(coordinator, switch)

    @property
    def name(self) -> str:
        """Get the name of the switch"""
        return (
            "ScreenLogic " + self.coordinator.data["circuits"][self._entity_id]["name"]
        )

    @property
    def is_on(self) -> bool:
        """Get whether the switch is in on state."""
        return self.coordinator.data["circuits"][self._entity_id]["value"] == 1

    async def async_turn_on(self, **kwargs) -> None:
        """Send the ON command."""
        if self.coordinator.gateway.set_circuit(self._entity_id, 1):
            _LOGGER.info("screenlogic turn on " + str(self._entity_id))
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.info("screenlogic turn on error")

    async def async_turn_off(self, **kwargs) -> None:
        """Send the OFF command."""
        if self.coordinator.gateway.set_circuit(self._entity_id, 0):
            _LOGGER.info("screenlogic turn of " + str(self._entity_id))
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.info("screenlogic turn off error")
