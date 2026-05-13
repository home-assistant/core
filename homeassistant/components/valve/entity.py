"""Base entity for the Valve platform."""

from dataclasses import dataclass
from typing import Any, final

from homeassistant.helpers.entity import Entity, EntityDescription

from .const import ValveDeviceClass, ValveEntityFeature, ValveState

ATTR_CURRENT_POSITION = "current_position"
ATTR_IS_CLOSED = "is_closed"


@dataclass(frozen=True, kw_only=True)
class ValveEntityDescription(EntityDescription):
    """A class that describes valve entities."""

    device_class: ValveDeviceClass | None = None
    reports_position: bool = False


class ValveEntity(Entity):
    """Base class for valve entities."""

    entity_description: ValveEntityDescription
    _attr_current_valve_position: int | None = None
    _attr_device_class: ValveDeviceClass | None
    _attr_is_closed: bool | None = None
    _attr_is_closing: bool | None = None
    _attr_is_opening: bool | None = None
    _attr_reports_position: bool
    _attr_supported_features: ValveEntityFeature = ValveEntityFeature(0)

    __is_last_toggle_direction_open = True

    @property
    def reports_position(self) -> bool:
        """Return True if entity reports position, False otherwise."""
        if hasattr(self, "_attr_reports_position"):
            return self._attr_reports_position
        if hasattr(self, "entity_description"):
            return self.entity_description.reports_position
        raise ValueError(f"'reports_position' not set for {self.entity_id}.")

    @property
    def current_valve_position(self) -> int | None:
        """Return current position of valve.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self._attr_current_valve_position

    @property
    def device_class(self) -> ValveDeviceClass | None:
        """Return the class of this entity."""
        if hasattr(self, "_attr_device_class"):
            return self._attr_device_class
        if hasattr(self, "entity_description"):
            return self.entity_description.device_class
        return None

    @property
    @final
    def state(self) -> str | None:
        """Return the state of the valve."""
        reports_position = self.reports_position
        if self.is_opening:
            self.__is_last_toggle_direction_open = True
            return ValveState.OPENING
        if self.is_closing:
            self.__is_last_toggle_direction_open = False
            return ValveState.CLOSING
        if reports_position is True:
            if (current_valve_position := self.current_valve_position) is None:
                return None
            position_zero = current_valve_position == 0
            return ValveState.CLOSED if position_zero else ValveState.OPEN
        if (closed := self.is_closed) is None:
            return None
        return ValveState.CLOSED if closed else ValveState.OPEN

    @final
    @property
    def state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        data: dict[str, Any] = {}

        if self.reports_position:
            if (current_valve_position := self.current_valve_position) is None:
                data[ATTR_IS_CLOSED] = None
            else:
                data[ATTR_IS_CLOSED] = current_valve_position == 0
            data[ATTR_CURRENT_POSITION] = current_valve_position
        else:
            data[ATTR_IS_CLOSED] = self.is_closed

        return data

    @property
    def supported_features(self) -> ValveEntityFeature:
        """Flag supported features."""
        return self._attr_supported_features

    @property
    def is_opening(self) -> bool | None:
        """Return if the valve is opening or not."""
        return self._attr_is_opening

    @property
    def is_closing(self) -> bool | None:
        """Return if the valve is closing or not."""
        return self._attr_is_closing

    @property
    def is_closed(self) -> bool | None:
        """Return if the valve is closed or not."""
        return self._attr_is_closed

    def open_valve(self) -> None:
        """Open the valve."""
        raise NotImplementedError

    async def async_open_valve(self) -> None:
        """Open the valve."""
        await self.hass.async_add_executor_job(self.open_valve)

    @final
    async def async_handle_open_valve(self) -> None:
        """Open the valve."""
        if self.supported_features & ValveEntityFeature.SET_POSITION:
            await self.async_set_valve_position(100)
            return
        await self.async_open_valve()

    def close_valve(self) -> None:
        """Close valve."""
        raise NotImplementedError

    async def async_close_valve(self) -> None:
        """Close valve."""
        await self.hass.async_add_executor_job(self.close_valve)

    @final
    async def async_handle_close_valve(self) -> None:
        """Close the valve."""
        if self.supported_features & ValveEntityFeature.SET_POSITION:
            await self.async_set_valve_position(0)
            return
        await self.async_close_valve()

    async def async_toggle(self) -> None:
        """Toggle the entity."""
        if self.supported_features & ValveEntityFeature.STOP and (
            self.is_closing or self.is_opening
        ):
            return await self.async_stop_valve()
        if self.is_closed:
            return await self.async_handle_open_valve()
        if self.__is_last_toggle_direction_open:
            return await self.async_handle_close_valve()
        return await self.async_handle_open_valve()

    def set_valve_position(self, position: int) -> None:
        """Move the valve to a specific position."""
        raise NotImplementedError

    async def async_set_valve_position(self, position: int) -> None:
        """Move the valve to a specific position."""
        await self.hass.async_add_executor_job(self.set_valve_position, position)

    def stop_valve(self) -> None:
        """Stop the valve."""
        raise NotImplementedError

    async def async_stop_valve(self) -> None:
        """Stop the valve."""
        await self.hass.async_add_executor_job(self.stop_valve)
