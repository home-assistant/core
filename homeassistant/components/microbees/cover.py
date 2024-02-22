"""Cover integration microBees."""
from threading import Timer
from typing import Any

from microBeesPy import Actuator

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import MicroBeesUpdateCoordinator
from .entity import MicroBeesEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Config entry."""
    coordinator: MicroBeesUpdateCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ].coordinator
    covers = []
    for bee_id, bee in coordinator.data.bees.items():
        if bee.productID == 47:
            actuator_up_id = next(filter(lambda x: x.deviceID == 551, bee.actuators)).id
            actuator_down_id = next(
                filter(lambda x: x.deviceID == 552, bee.actuators)
            ).id
            covers.append(
                MBCover(coordinator, bee_id, actuator_up_id, actuator_down_id)
            )
    async_add_entities(covers)


class MBCover(MicroBeesEntity, CoverEntity):
    """Representation of a microBees cover."""

    def __init__(self, coordinator, bee_id, actuator_up_id, actuator_down_id) -> None:
        """Initialize the microBees cover."""
        super().__init__(coordinator, bee_id)
        self.actuator_up_id = actuator_up_id
        self.actuator_down_id = actuator_down_id
        self.attr_supported_features = {
            CoverEntityFeature.OPEN,
            CoverEntityFeature.STOP,
            CoverEntityFeature.CLOSE,
        }
        self._attr_is_closed = None

    _attr_device_class = CoverDeviceClass.SHUTTER

    @property
    def name(self) -> str:
        """Name of the cover."""
        return self.bee.name

    @property
    def actuator_up(self) -> Actuator:
        """Return the rolling up actuator."""
        return self.coordinator.data.actuators[self.actuator_up_id]

    @property
    def actuator_down(self) -> Actuator:
        """Return the rolling down actuator."""
        return self.coordinator.data.actuators[self.actuator_down_id]

    def reset_open_close(self):
        """Reset the opening and closing state."""
        self._attr_is_opening = False
        self._attr_is_closing = None
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        sendCommand = await self.coordinator.microbees.sendCommand(
            self.actuator_up_id,
            self.actuator_up.configuration.actuator_timing * 1000,
        )
        if sendCommand:
            self._attr_is_opening = True
            Timer(
                self.actuator_up.configuration.actuator_timing,
                self.reset_open_close,
            ).start()
        else:
            raise HomeAssistantError(f"Failed to turn off {self.name}")

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        sendCommand = await self.coordinator.microbees.sendCommand(
            self.actuator_down_id,
            self.actuator_down.configuration.actuator_timing * 1000,
        )
        if sendCommand:
            self._attr_is_closing = True
            Timer(
                self.actuator_up.configuration.actuator_timing,
                self.reset_open_close,
            ).start()
        else:
            raise HomeAssistantError(f"Failed to turn off {self.name}")

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        if self.is_opening:
            await self.coordinator.microbees.sendCommand(self.actuator_up_id, 0)
        if self.is_closing:
            await self.coordinator.microbees.sendCommand(self.actuator_down_id, 0)
