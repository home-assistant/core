"""Platform for valve integration."""

from typing import TYPE_CHECKING, override

from boschshcpy import SHCThermostat

from homeassistant.components.valve import ValveDeviceClass, ValveEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoschConfigEntry
from .entity import SHCEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SHC valve platform."""
    session = config_entry.runtime_data

    shc_info = session.information
    if TYPE_CHECKING:
        assert shc_info is not None and shc_info.unique_id is not None

    async_add_entities(
        SHCValve(
            hass=hass,
            device=device,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
        )
        for device in session.device_helper.thermostats
    )


class SHCValve(SHCEntity, ValveEntity):
    """Representation of a SHC thermostat valve position."""

    _attr_device_class = ValveDeviceClass.WATER
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_reports_position = True
    _attr_translation_key = "valve"
    _device: SHCThermostat

    @property
    @override
    def current_valve_position(self) -> int | None:
        """Return current position of valve.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return self._device.position
