"""Support for Appartme light control functionality."""

import logging

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Appartme light platform."""
    # Access the devices and API from hass.data
    data = hass.data[DOMAIN][config_entry.entry_id]
    devices_info = data["devices_info"]
    api = data["api"]
    coordinators = data["coordinators"]

    # Create light entities only for devices with 'lighting' property
    lights = []
    for device_info in devices_info:
        device_id = device_info["deviceId"]
        coordinator = coordinators[device_id]
        if not coordinator:
            _LOGGER.warning("No coordinator found for device %s. Skipping", device_id)
            continue

        lights.extend(
            [
                AppartmeLight(
                    api,
                    device_info,
                    prop["propertyId"],
                    coordinator,
                )
                for prop in device_info.get("properties", [])
                if prop["propertyId"] == "lighting"
            ]
        )

    # Add the light entities to Home Assistant
    async_add_entities(lights)


class AppartmeLight(CoordinatorEntity, LightEntity):
    """Representation of an Appartme light."""

    def __init__(self, api, device_info, property_id, coordinator):
        """Initialize the light."""
        super().__init__(coordinator)
        self._api = api
        self._device_id = device_info["deviceId"]
        self._device_name = device_info["name"]
        self._property_id = property_id
        self._attr_supported_color_modes = {ColorMode.ONOFF}
        self._attr_translation_key = property_id
        self._attr_has_entity_name = True

        # Optimistic state attributes
        self._attr_is_on = None

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
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        return f"{self._device_id}_{self._property_id}"

    @property
    def color_mode(self):
        """Return the color mode."""
        return ColorMode.ONOFF

    @property
    def is_on(self) -> bool:
        """Return true if the light is on."""
        # Because of optimistic update state
        if self._attr_is_on is not None:
            return self._attr_is_on

        data = self.coordinator.data
        if data is None:
            return False
        for prop in data.get("values", []):
            if prop["propertyId"] == self._property_id:
                return bool(prop["value"])
        return False

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        try:
            await self._api.set_device_property_value(
                self._device_id, self._property_id, True
            )
            # Optimistically update the state
            self._attr_is_on = True
            self.async_write_ha_state()
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Error turning on light for %s: %s", self.name, err)

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        try:
            await self._api.set_device_property_value(
                self._device_id, self._property_id, False
            )
            # Optimistically update the state
            self._attr_is_on = False
            self.async_write_ha_state()
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Error turning off light for %s: %s", self.name, err)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data
        if data is None:
            return

        self._attr_is_on = None

        self.async_write_ha_state()
