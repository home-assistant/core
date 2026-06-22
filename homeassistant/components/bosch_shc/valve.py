"""Platform for valve integration."""

from __future__ import annotations

from boschshcpy import SHCThermostat, SHCSession
from boschshcpy.device import SHCDevice

from homeassistant.components.valve import (
    ValveDeviceClass,
    ValveEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_SESSION, DOMAIN, LOGGER
from .entity import SHCEntity, device_excluded

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SHC valve platform."""
    entities: list[ValveEntity] = []
    session: SHCSession = hass.data[DOMAIN][config_entry.entry_id][DATA_SESSION]

    for valve in session.device_helper.thermostats:
        if device_excluded(valve, config_entry.options):
            continue
        entities.append(
            SHCValve(
                device=valve,
                entry_id=config_entry.entry_id,
                attr_name="Valve",
            )
        )

    if entities:
        async_add_entities(entities)


class SHCValve(SHCEntity, ValveEntity):
    """Representation of a SHC valve."""

    _attr_device_class = ValveDeviceClass.WATER
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_reports_position = True

    def __init__(
        self,
        device: SHCDevice,
        entry_id: str,
        attr_name: str | None = None,
    ) -> None:
        """Initialize a SHC valve."""
        super().__init__(device, entry_id)
        self._attr_name = None if attr_name is None else attr_name
        self._attr_unique_id = (
            f"{device.root_device_id}_{device.id}"
            if attr_name is None
            else f"{device.root_device_id}_{device.id}_{attr_name.lower()}"
        )
        self._device: SHCThermostat = device

    @property
    def current_valve_position(self) -> int | None:
        """Return current position of valve.

        None is unknown, 0 is closed, 100 is fully open.
        """
        try:
            return self._device.position
        except (ValueError, KeyError, AttributeError) as err:
            LOGGER.debug(
                "Could not read valve position for %s: %s", self._device.name, err
            )
            return None
