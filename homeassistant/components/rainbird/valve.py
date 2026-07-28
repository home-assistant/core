"""Support for Rain Bird Irrigation system LNK Wi-Fi Module."""

import logging
from typing import Any, override

from pyrainbird.exceptions import RainbirdApiException, RainbirdDeviceBusyException

from homeassistant.components.valve import (
    ValveDeviceClass,
    ValveEntity,
    ValveEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_DURATION,
    CONF_IMPORTED_NAMES,
    CONF_ZONE_TYPE,
    DOMAIN,
    MANUFACTURER,
    ZONE_TYPE_VALVE,
)
from .coordinator import RainbirdUpdateCoordinator
from .types import RainbirdConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RainbirdConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry for Rain Bird irrigation valves."""
    if config_entry.options.get(CONF_ZONE_TYPE) != ZONE_TYPE_VALVE:
        return
    coordinator = config_entry.runtime_data.coordinator
    async_add_entities(
        RainBirdValve(
            coordinator,
            zone,
            config_entry.options[ATTR_DURATION],
            config_entry.data.get(CONF_IMPORTED_NAMES, {}).get(str(zone)),
        )
        for zone in coordinator.data.zones
    )


class RainBirdValve(CoordinatorEntity[RainbirdUpdateCoordinator], ValveEntity):
    """Representation of a Rain Bird valve."""

    _attr_device_class = ValveDeviceClass.WATER
    _attr_reports_position = False
    _attr_supported_features = ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE

    def __init__(
        self,
        coordinator: RainbirdUpdateCoordinator,
        zone: int,
        duration_minutes: int,
        imported_name: str | None,
    ) -> None:
        """Initialize a Rain Bird Valve Device."""
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

    @override
    async def async_open_valve(self, **kwargs: Any) -> None:
        """Open the valve."""
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

    @override
    async def async_close_valve(self) -> None:
        """Close the valve."""
        try:
            await self.coordinator.controller.stop_irrigation()
        except RainbirdDeviceBusyException as err:
            raise HomeAssistantError(
                "Rain Bird device is busy; Wait and try again"
            ) from err
        except RainbirdApiException as err:
            raise HomeAssistantError("Rain Bird device failure") from err

        if self.is_closed is False:
            self.coordinator.data.active_zones.remove(self._zone)
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    @property
    @override
    def is_closed(self) -> bool:
        """Return true if valve is closed."""
        return self._zone not in self.coordinator.data.active_zones
