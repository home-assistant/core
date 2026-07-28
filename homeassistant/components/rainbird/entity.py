"""Rain Bird entity classes."""

from typing import Any, override

from pyrainbird.exceptions import RainbirdApiException, RainbirdDeviceBusyException

from homeassistant.components.valve import (
    ValveDeviceClass,
    ValveEntity,
    ValveEntityFeature,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_DURATION, DOMAIN, MANUFACTURER
from .coordinator import RainbirdUpdateCoordinator


class RainBirdZoneEntity(CoordinatorEntity[RainbirdUpdateCoordinator]):
    """Base entity for a Rain Bird irrigation zone."""

    def __init__(
        self,
        coordinator: RainbirdUpdateCoordinator,
        zone: int,
        duration_minutes: int,
        imported_name: str | None,
    ) -> None:
        """Initialize a Rain Bird zone entity."""
        super().__init__(coordinator)
        self._zone = zone
        if coordinator.unique_id is not None:
            self._attr_unique_id = f"{coordinator.unique_id}-{zone}"
        device_name = f"{MANUFACTURER} Sprinkler {zone}"
        if imported_name:
            self._attr_name = imported_name
            self._attr_has_entity_name = False
        else:
            self._attr_name = None if coordinator.unique_id is not None else device_name
            self._attr_has_entity_name = True
        self._duration_minutes = duration_minutes
        if coordinator.unique_id is not None and self._attr_unique_id is not None:
            self._attr_device_info = DeviceInfo(
                name=device_name,
                identifiers={(DOMAIN, self._attr_unique_id)},
                manufacturer=MANUFACTURER,
                via_device=(DOMAIN, coordinator.unique_id),
            )

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return state attributes."""
        return {"zone": self._zone}

    async def _async_irrigate(self, **kwargs: Any) -> None:
        """Start irrigation for this zone."""
        try:
            await self.coordinator.controller.irrigate_zone(
                int(self._zone),
                int(kwargs.get(ATTR_DURATION, self._duration_minutes)),
            )
        except RainbirdDeviceBusyException as err:
            raise HomeAssistantError(
                "Rain Bird device is busy; Wait and try again"
            ) from err
        except RainbirdApiException as err:
            raise HomeAssistantError("Rain Bird device failure") from err

        self.coordinator.data.active_zones.add(self._zone)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def _async_stop_irrigation(self) -> None:
        """Stop irrigation for this zone."""
        try:
            await self.coordinator.controller.stop_irrigation()
        except RainbirdDeviceBusyException as err:
            raise HomeAssistantError(
                "Rain Bird device is busy; Wait and try again"
            ) from err
        except RainbirdApiException as err:
            raise HomeAssistantError("Rain Bird device failure") from err

        if self._zone in self.coordinator.data.active_zones:
            self.coordinator.data.active_zones.remove(self._zone)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


class RainBirdValve(RainBirdZoneEntity, ValveEntity):
    """Representation of a Rain Bird valve."""

    _attr_device_class = ValveDeviceClass.WATER
    _attr_reports_position = False
    _attr_supported_features = ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE

    @override
    async def async_open_valve(self, **kwargs: Any) -> None:
        """Open the valve."""
        await self._async_irrigate(**kwargs)

    @override
    async def async_close_valve(self) -> None:
        """Close the valve."""
        await self._async_stop_irrigation()

    @property
    @override
    def is_closed(self) -> bool:
        """Return true if valve is closed."""
        return self._zone not in self.coordinator.data.active_zones
