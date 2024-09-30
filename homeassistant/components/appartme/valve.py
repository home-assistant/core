"""Support for Appartme water valve control functionality."""

import logging

from homeassistant.components.valve import ValveEntity, ValveEntityFeature
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Appartme valve platform."""
    # Access the devices and API from hass.data
    data = hass.data[DOMAIN][config_entry.entry_id]
    devices_info = data["devices_info"]
    api = data["api"]
    coordinators = data["coordinators"]

    # Create valve entities only for devices with property 'water'
    water_valves = []
    for device_info in devices_info:
        device_id = device_info["deviceId"]
        coordinator = coordinators.get(device_id)
        if not coordinator:
            _LOGGER.warning("No coordinator found for device %s. Skipping", device_id)
            continue

        water_valves.extend(
            [
                AppartmeWaterValve(
                    api,
                    device_info,
                    prop["propertyId"],
                    coordinator,
                )
                for prop in device_info.get("properties", [])
                if prop["propertyId"] == "water"
            ]
        )

    if not water_valves:
        _LOGGER.warning("No valve entities to add")
        return

    # Add the water valve entities to Home Assistant
    async_add_entities(water_valves)


class AppartmeWaterValve(CoordinatorEntity, ValveEntity):
    """Representation of an Appartme water valve."""

    def __init__(self, api, device_info, property_id, coordinator):
        """Initialize the valve."""
        super().__init__(coordinator)
        self._api = api
        self._device_id = device_info["deviceId"]
        self._device_name = device_info["name"]
        self._property_id = property_id
        self._attr_translation_key = property_id
        self._attr_has_entity_name = True

        # Optimistic state attributes
        self._attr_is_closed = None

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return self.coordinator.last_update_success

    @property
    def device_info(self):
        """Return device information to link this entity to a device."""
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device_name,
            "manufacturer": "Appartme",
            "model": "Main Module",
            "sw_version": self._device_id,
        }

    @property
    def unique_id(self):
        """Return a unique ID to use for this entity."""
        return f"{self._device_id}_{self._property_id}"

    @property
    def is_closed(self):
        """Return true if the valve is closed."""
        # Because of optimistic update state
        if self._attr_is_closed is not None:
            return self._attr_is_closed

        data = self.coordinator.data
        if data is None:
            return None
        for prop in data.get("values", []):
            if prop["propertyId"] == self._property_id:
                return not bool(prop["value"])
        return None

    @property
    def current_valve_position(self):
        """Return the current position of the valve (0-100), or None if not reported."""
        # Because of optimistic update state
        if self._attr_is_closed is not None:
            if self.reports_position:
                return int(self._attr_is_closed)
            return 0 if not bool(self._attr_is_closed) else 100

        data = self.coordinator.data
        if data is None:
            return None
        for prop in data.get("values", []):
            if prop["propertyId"] == self._property_id:
                if self.reports_position:
                    return int(prop["value"])
                return 0 if not bool(prop["value"]) else 100
        return None

    @property
    def reports_position(self):
        """Indicate if the valve reports its position."""
        return False  # Set to True if your valve reports position

    @property
    def supported_features(self):
        """Return the supported features for this valve."""
        return ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE

    async def async_open_valve(self, **kwargs):
        """Open the valve."""
        try:
            await self._api.set_device_property_value(
                self._device_id, self._property_id, True
            )
            # Optimistically update the state
            self._attr_is_closed = False
            self.async_write_ha_state()
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Error opening valve for %s: %s", self.name, err)

    async def async_close_valve(self, **kwargs):
        """Close the valve."""
        try:
            await self._api.set_device_property_value(
                self._device_id, self._property_id, False
            )
            # Optimistically update the state
            self._attr_is_closed = True
            self.async_write_ha_state()
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Error closing valve for %s: %s", self.name, err)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Reset _attr_is_closed to use the latest data from coordinator
        self._attr_is_closed = None
        self.async_write_ha_state()
