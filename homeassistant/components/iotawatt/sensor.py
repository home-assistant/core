"""Support for IoTaWatt Energy monitor."""
from __future__ import annotations

from iotawattpy.sensor import Sensor

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import callback
from homeassistant.helpers import entity_registry, update_coordinator

from .const import DOMAIN, ENTITY_DESCRIPTION_KEY_MAP
from .coordinator import IotawattUpdater


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add sensors for passed config_entry in HA."""
    coordinator: IotawattUpdater = hass.data[DOMAIN][config_entry.entry_id]
    created = set()

    @callback
    def _create_entity(key: str) -> IotaWattSensor:
        """Create a sensor entity."""
        created.add(key)
        return IotaWattSensor(
            coordinator=coordinator,
            key=key,
            mac_address=coordinator.data["sensors"][key].hub_mac_address,
            name=coordinator.data["sensors"][key].getName(),
            entity_description=ENTITY_DESCRIPTION_KEY_MAP.get(
                coordinator.data["sensors"][key].getUnit(),
                SensorEntityDescription("base_sensor"),
            ),
        )

    async_add_entities(_create_entity(key) for key in coordinator.data["sensors"])

    @callback
    def new_data_received():
        """Check for new sensors."""
        entities = [
            _create_entity(key)
            for key in coordinator.data["sensors"]
            if key not in created
        ]
        if entities:
            async_add_entities(entities)

    coordinator.async_add_listener(new_data_received)


class IotaWattSensor(update_coordinator.CoordinatorEntity, SensorEntity):
    """Defines a IoTaWatt Energy Sensor."""

    _attr_force_update = True
    _attr_icon = "mdi:flash"

    def __init__(self, coordinator, key, mac_address, name, entity_description):
        """Initialize the sensor."""
        super().__init__(coordinator=coordinator)

        self._key = key
        self._attr_unique_id = self._sensor_data.getSensorID()
        self.entity_description = entity_description

    @property
    def _sensor_data(self) -> Sensor:
        """Return sensor data."""
        return self.coordinator.data["sensors"][self._key]

    @property
    def name(self) -> str | None:
        """Return name of the entity."""
        return self._sensor_data.getName()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._key not in self.coordinator.data["sensors"]:
            entity_registry.async_get(self.hass).async_remove(self.entity_id)
            return

        super()._handle_coordinator_update()

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        data = self._sensor_data
        attrs = {"type": data.getType()}
        if attrs["type"] == "Input":
            attrs["channel"] = data.getChannel()

        return attrs

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._sensor_data.getValue()
