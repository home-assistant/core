"""Support for a ScreenLogic 'circuit' switch."""
import logging

from screenlogicpy.const import ON_OFF

from homeassistant.components.switch import SwitchEntity

from . import ScreenlogicEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up entry."""
    entities = []
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = data["coordinator"]

    for switch in data["devices"]["switch"]:
        entities.append(ScreenLogicSwitch(coordinator, switch))
    async_add_entities(entities)


class ScreenLogicSwitch(ScreenlogicEntity, SwitchEntity):
    """ScreenLogic switch entity."""

    @property
    def name(self):
        """Get the name of the switch."""
        return f"{self.gateway_name} {self.circuit['name']}"

    @property
    def is_on(self) -> bool:
        """Get whether the switch is in on state."""
        return self.circuit["value"] == 1

    async def async_turn_on(self, **kwargs) -> None:
        """Send the ON command."""
        return await self._async_set_circuit(ON_OFF.ON)

    async def async_turn_off(self, **kwargs) -> None:
        """Send the OFF command."""
        return await self._async_set_circuit(ON_OFF.OFF)

    async def _async_set_circuit(self, circuit_value) -> None:
        async with self.coordinator.api_lock:
            success = await self.hass.async_add_executor_job(
                self.gateway.set_circuit, self._data_key, circuit_value
            )

        if success:
            _LOGGER.debug("Turn %s %s", self._data_key, circuit_value)
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.warning(
                "Failed to set_circuit %s %s", self._data_key, circuit_value
            )

    @property
    def circuit(self):
        """Shortcut to access the circuit."""
        return self.coordinator.data["circuits"][self._data_key]
