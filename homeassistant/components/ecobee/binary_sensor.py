"""Support for Ecobee binary sensors."""

from typing import Any, override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EcobeeConfigEntry, EcobeeData
from .const import (
    DOMAIN,
    ECOBEE_ALERT_NUMBER_TO_TRANSLATION_KEY,
    ECOBEE_EQUIPMENT_TYPE_TO_ALERT_NUMBER,
    ECOBEE_MODEL_TO_NAME,
    MANUFACTURER,
)
from .entity import EcobeeBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EcobeeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ecobee binary (occupancy) sensors and alert sensors."""
    data = config_entry.runtime_data
    entities: list[BinarySensorEntity] = []

    for index in range(len(data.ecobee.thermostats)):
        for sensor in data.ecobee.get_remote_sensors(index):
            for item in sensor["capability"]:
                if item["type"] != "occupancy":
                    continue
                entities.append(EcobeeBinarySensor(data, sensor["name"], index))

        for equipment in data.ecobee.get_equipment_notifications(index):
            if not equipment.get("enabled"):
                continue
            equipment_type = equipment.get("type")
            alert_number = ECOBEE_EQUIPMENT_TYPE_TO_ALERT_NUMBER.get(equipment_type)
            if alert_number is None:
                continue
            entities.append(
                EcobeeAlertBinarySensor(data, index, alert_number, equipment_type)
            )

    async_add_entities(entities, True)


class EcobeeBinarySensor(BinarySensorEntity):
    """Representation of an Ecobee sensor."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY
    _attr_has_entity_name = True

    def __init__(self, data, sensor_name, sensor_index):
        """Initialize the Ecobee sensor."""
        self.data = data
        self.sensor_name = sensor_name
        self.index = sensor_index

    @property
    @override
    def unique_id(self) -> str | None:
        """Return a unique identifier for this sensor."""
        for sensor in self.data.ecobee.get_remote_sensors(self.index):
            if sensor["name"] == self.sensor_name:
                if "code" in sensor:
                    return f"{sensor['code']}-{self.device_class}"
                thermostat = self.data.ecobee.get_thermostat(self.index)
                return f"{thermostat['identifier']}-{sensor['id']}-{self.device_class}"
        return None

    @property
    @override
    def device_info(self) -> DeviceInfo | None:
        """Return device information for this sensor."""
        identifier = None
        model = None
        for sensor in self.data.ecobee.get_remote_sensors(self.index):
            if sensor["name"] != self.sensor_name:
                continue
            if "code" in sensor:
                identifier = sensor["code"]
                model = "ecobee Room Sensor"
            else:
                thermostat = self.data.ecobee.get_thermostat(self.index)
                identifier = thermostat["identifier"]
                try:
                    model = (
                        f"{ECOBEE_MODEL_TO_NAME[thermostat['modelNumber']]} Thermostat"
                    )
                except KeyError:
                    # Ecobee model is not in our list
                    model = None
            break

        if identifier is not None:
            return DeviceInfo(
                identifiers={(DOMAIN, identifier)},
                manufacturer=MANUFACTURER,
                model=model,
                name=self.sensor_name,
            )
        return None

    @property
    @override
    def available(self) -> bool:
        """Return true if device is available."""
        thermostat = self.data.ecobee.get_thermostat(self.index)
        return thermostat["runtime"]["connected"]

    async def async_update(self) -> None:
        """Get the latest state of the sensor."""
        await self.data.update()
        for sensor in self.data.ecobee.get_remote_sensors(self.index):
            if sensor["name"] != self.sensor_name:
                continue
            for item in sensor["capability"]:
                if item["type"] != "occupancy":
                    continue
                self._attr_is_on = item["value"] == "true"
                break


class EcobeeAlertBinarySensor(EcobeeBaseEntity, BinarySensorEntity):
    """Binary sensor that tracks an ecobee equipment maintenance reminder."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self,
        data: EcobeeData,
        thermostat_index: int,
        alert_number: int,
        equipment_type: str,
    ) -> None:
        """Initialize the alert sensor."""
        super().__init__(data, thermostat_index)
        self._alert_number = alert_number
        self._equipment_type = equipment_type
        self._attr_unique_id = f"{self.base_unique_id}_alert_{alert_number}"
        self._attr_translation_key = ECOBEE_ALERT_NUMBER_TO_TRANSLATION_KEY.get(
            alert_number
        )

    async def async_update(self) -> None:
        """Get the latest state from the thermostat."""
        await self.data.update()
        thermostat = self.thermostat
        is_firing = False
        self._attr_extra_state_attributes: dict[str, Any] = {
            "alert_number": self._alert_number,
            "equipment_type": self._equipment_type,
        }
        for alert in thermostat.get("alerts", []):
            if alert.get("alertNumber") == self._alert_number:
                is_firing = True
                self._attr_extra_state_attributes.update(
                    {
                        "date": alert.get("date"),
                        "time": alert.get("time"),
                        "text": alert.get("text"),
                        "alert_type": alert.get("alertType"),
                        "severity": alert.get("severity"),
                    }
                )
                break
        self._attr_is_on = is_firing
