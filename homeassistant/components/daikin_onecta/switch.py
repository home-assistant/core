"""Support for Daikin AirBase zones."""

import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import DaikinSwitch

if TYPE_CHECKING:
    from .coordinator import OnectaDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daikin switches based on config_entry."""
    coordinator: OnectaDataUpdateCoordinator = config_entry.runtime_data
    sensors = []
    supported_management_point_types = {
        "domesticHotWaterTank",
        "domesticHotWaterFlowThrough",
        "climateControl",
        "climateControlMainZone",
    }

    for device in (coordinator.data or {}).values():
        for management_point in device.device.management_points:
            management_point_type = management_point.management_point_type
            for (
                value,
                characteristic,
            ) in management_point.simple_characteristics().items():
                values = characteristic.values or []
                if (
                    characteristic.value is not None
                    and characteristic.settable
                    and "on" in values
                    and "off" in values
                ):
                    if (
                        value == "onOffMode"
                        and management_point_type in supported_management_point_types
                    ):
                        continue
                    if (
                        value == "powerfulMode"
                        and management_point_type in supported_management_point_types
                    ):
                        continue
                    sensors.append(
                        DaikinSwitch(
                            device,
                            coordinator,
                            management_point.embedded_id,
                            management_point_type,
                            value,
                        )
                    )

    async_add_entities(sensors)
