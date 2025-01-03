"""Support for Watergate Valve."""

from homeassistant.components.sensor import Any, HomeAssistant
from homeassistant.components.valve import (
    ValveDeviceClass,
    ValveEntity,
    ValveEntityFeature,
    ValveState,
)
from homeassistant.core import callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WatergateConfigEntry
from .coordinator import WatergateDataCoordinator
from .entity import WatergateEntity

ENTITY_NAME = "valve"
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WatergateConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up all entries for Watergate Platform."""

    async_add_entities([SonicValve(config_entry.runtime_data)])


class SonicValve(WatergateEntity, ValveEntity):
    """Define a Sonic Valve entity."""

    _attr_supported_features = ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE
    _attr_reports_position = False
    _valve_state: str | None = None
    _attr_device_class = ValveDeviceClass.WATER
    _attr_name = None

    def __init__(
        self,
        coordinator: WatergateDataCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, ENTITY_NAME)
        self._valve_state = (
            coordinator.data.state.valve_state if coordinator.data.state else None
        )

    @property
    def is_closed(self) -> bool:
        """Return if the valve is closed or not."""
        return self._valve_state == ValveState.CLOSED

    @property
    def is_opening(self) -> bool | None:
        """Return if the valve is opening or not."""
        return self._valve_state == ValveState.OPENING

    @property
    def is_closing(self) -> bool | None:
        """Return if the valve is closing or not."""
        return self._valve_state == ValveState.CLOSING

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""
        self._attr_available = self.coordinator.data is not None
        self._valve_state = (
            self.coordinator.data.state.valve_state
            if self.coordinator.data.state
            else None
        )
        self.async_write_ha_state()

    async def async_open_valve(self, **kwargs: Any) -> None:
        """Open the valve."""
        await self._api_client.async_set_valve_state(ValveState.OPEN)
        self._valve_state = ValveState.OPENING
        self.async_write_ha_state()

    async def async_close_valve(self, **kwargs: Any) -> None:
        """Close the valve."""
        await self._api_client.async_set_valve_state(ValveState.CLOSED)
        self._valve_state = ValveState.CLOSING
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.coordinator.data.state is not None
