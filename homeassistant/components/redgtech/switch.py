import logging
from typing import Any
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import STATE_ON, STATE_OFF
from .const import DOMAIN
from .coordinator import RedgtechDataUpdateCoordinator, RedgtechDevice
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the switch platform."""

    coordinator = config_entry.runtime_data

    switches = []
    for device in coordinator.data:
        switches.append(RedgtechSwitch(coordinator, device))

    async_add_entities(switches)

class RedgtechSwitch(CoordinatorEntity[RedgtechDataUpdateCoordinator], SwitchEntity):
    """Representation of a Redgtech switch."""

    _attr_has_entity_name: bool = True

    def __init__(self, coordinator: RedgtechDataUpdateCoordinator, device: RedgtechDevice) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.device = device
        self.api: Any = coordinator.api
        self._state: bool = device.state == STATE_ON
        self._name: str = device.name
        self._endpoint_id: str = device.id
        self._attr_unique_id: str = f"redgtech_{self._endpoint_id}"

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self.device.name

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self.device.state == STATE_ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            await self.coordinator.set_device_state(self.device.id, True)
            await self.coordinator.async_request_refresh()
            self.device.state = STATE_ON
            self.async_write_ha_state()
        except Exception as e:
            raise HomeAssistantError(f"Failed to turn on switch {self.device.name}: {e}")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            await self.coordinator.set_device_state(self.device.id, False)
            await self.coordinator.async_request_refresh()
            self.device.state = STATE_OFF
            self.async_write_ha_state()
        except Exception as e:
            raise HomeAssistantError(f"Failed to turn off switch {self.device.name}: {e}")

    async def async_update(self) -> None:
        """Fetch new state data for the switch."""
        try:
            await self.coordinator.async_request_refresh()
            self._state = self.device.state == STATE_ON
            self.async_write_ha_state()
        except Exception as e:
            raise HomeAssistantError(f"Failed to update switch {self.device.name}: {e}")
