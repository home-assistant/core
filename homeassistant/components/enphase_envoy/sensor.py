"""Support for Enphase Envoy solar energy monitor."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import COORDINATOR, DOMAIN, NAME, SENSORS

ICON = "mdi:flash"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up envoy sensor platform."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = data[COORDINATOR]
    name = data[NAME]

    entities = []
    for sensor_description in SENSORS:
        if (
            sensor_description.key == "inverters"
            and coordinator.data.get("inverters_production") is not None
        ):
            for inverter in coordinator.data["inverters_production"]:
                entity_name = f"{name} {sensor_description.name} {inverter}"
                split_name = entity_name.split(" ")
                serial_number = split_name[-1]
                entities.append(
                    Envoy(
                        sensor_description,
                        entity_name,
                        name,
                        config_entry.unique_id,
                        serial_number,
                        coordinator,
                    )
                )
        elif sensor_description.key != "inverters":
            data = coordinator.data.get(sensor_description.key)
            if isinstance(data, str) and "not available" in data:
                continue

            entity_name = f"{name} {sensor_description.name}"
            entities.append(
                Envoy(
                    sensor_description,
                    entity_name,
                    name,
                    config_entry.unique_id,
                    None,
                    coordinator,
                )
            )

    async_add_entities(entities)


class Envoy(CoordinatorEntity, SensorEntity):
    """Envoy entity."""

    def __init__(
        self,
        description,
        name,
        device_name,
        device_serial_number,
        serial_number,
        coordinator,
    ):
        """Initialize Envoy entity."""
        self.entity_description = description
        self._name = name
        self._serial_number = serial_number
        self._device_name = device_name
        self._device_serial_number = device_serial_number

        super().__init__(coordinator)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        if self._serial_number:
            return self._serial_number
        if self._device_serial_number:
            return f"{self._device_serial_number}_{self.entity_description.key}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.entity_description.key != "inverters":
            value = self.coordinator.data.get(self.entity_description.key)

        elif (
            self.entity_description.key == "inverters"
            and self.coordinator.data.get("inverters_production") is not None
        ):
            value = self.coordinator.data.get("inverters_production").get(
                self._serial_number
            )[0]
        else:
            return None

        return value

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if (
            self.entity_description.key == "inverters"
            and self.coordinator.data.get("inverters_production") is not None
        ):
            value = self.coordinator.data.get("inverters_production").get(
                self._serial_number
            )[1]
            return {"last_reported": value}

        return None

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return the device_info of the device."""
        if not self._device_serial_number:
            return None
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._device_serial_number))},
            manufacturer="Enphase",
            model="Envoy",
            name=self._device_name,
        )
