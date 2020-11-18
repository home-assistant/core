"""Support for Google Nest SDM sensors."""

from typing import Optional

from google_nest_sdm.device import Device
from google_nest_sdm.device_traits import HumidityTrait, InfoTrait, TemperatureTrait

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    TEMP_CELSIUS,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN, SIGNAL_NEST_UPDATE

DEVICE_TYPE_MAP = {
    "sdm.devices.types.CAMERA": "Camera",
    "sdm.devices.types.DISPLAY": "Display",
    "sdm.devices.types.DOORBELL": "Doorbell",
    "sdm.devices.types.THERMOSTAT": "Thermostat",
}


async def async_setup_sdm_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the sensors."""

    subscriber = hass.data[DOMAIN][entry.entry_id]
    device_manager = await subscriber.async_device_manager

    # Fetch initial data so we have data when entities subscribe.

    entities = []
    for device in device_manager.devices.values():
        if TemperatureTrait.NAME in device.traits:
            entities.append(TemperatureSensor(device))
        if HumidityTrait.NAME in device.traits:
            entities.append(HumiditySensor(device))
    async_add_entities(entities)


class SensorBase(Entity):
    """Representation of a dynamically updated Sensor."""

    def __init__(self, device: Device):
        """Initialize the sensor."""
        self._device = device

    @property
    def should_poll(self) -> bool:
        """Disable polling since entities have state pushed via pubsub."""
        return False

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        # The API "name" field is a unique device identifier.
        return f"{self._device.name}-{self.device_class}"

    @property
    def device_name(self):
        """Return the name of the physical device that includes the sensor."""
        if InfoTrait.NAME in self._device.traits:
            trait = self._device.traits[InfoTrait.NAME]
            if trait.custom_name:
                return trait.custom_name
        # Build a name from the room/structure.  Note: This room/structure name
        # is not associated with a home assistant Area.
        parent_relations = self._device.parent_relations
        if parent_relations:
            items = sorted(parent_relations.items())
            names = [name for id, name in items]
            return " ".join(names)
        return self.unique_id

    @property
    def device_info(self):
        """Return device specific attributes."""
        return {
            # The API "name" field is a unique device identifier.
            "identifiers": {(DOMAIN, self._device.name)},
            "name": self.device_name,
            "manufacturer": "Google Nest",
            "model": self.device_model,
        }

    @property
    def device_model(self):
        """Return device model information."""
        # The API intentionally returns minimal information about specific
        # devices, instead relying on traits, but we can infer a generic model
        # name based on the type
        return DEVICE_TYPE_MAP.get(self._device.type)

    async def async_added_to_hass(self):
        """Run when entity is added to register update signal handler."""
        # Event messages trigger the SIGNAL_NEST_UPDATE, which is intercepted
        # here to re-fresh the signals from _device.  Unregister this callback
        # when the entity is removed.
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_NEST_UPDATE,
                self.async_write_ha_state,
            )
        )


class TemperatureSensor(SensorBase):
    """Representation of a Temperature Sensor."""

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.device_name} Temperature"

    @property
    def state(self):
        """Return the state of the sensor."""
        trait = self._device.traits[TemperatureTrait.NAME]
        return trait.ambient_temperature_celsius

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def device_class(self):
        """Return the class of this device."""
        return DEVICE_CLASS_TEMPERATURE


class HumiditySensor(SensorBase):
    """Representation of a Humidity Sensor."""

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        # The API returns the identifier under the name field.
        return f"{self._device.name}-humidity"

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.device_name} Humidity"

    @property
    def state(self):
        """Return the state of the sensor."""
        trait = self._device.traits[HumidityTrait.NAME]
        return trait.ambient_humidity_percent

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return PERCENTAGE

    @property
    def device_class(self):
        """Return the class of this device."""
        return DEVICE_CLASS_HUMIDITY
