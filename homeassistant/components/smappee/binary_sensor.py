"""Support for monitoring a Smappee appliance binary sensor."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

BINARY_SENSOR_PREFIX = "Appliance"
PRESENCE_PREFIX = "Presence"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smappee binary sensor."""
    smappee_base = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[BinarySensorEntity] = []
    for service_location in smappee_base.smappee.service_locations.values():
        for appliance_id, appliance in service_location.appliances.items():
            if appliance.type != "Find me" and appliance.source_type == "NILM":
                entities.append(
                    SmappeeAppliance(
                        smappee_base=smappee_base,
                        service_location=service_location,
                        appliance_id=appliance_id,
                        appliance_name=appliance.name,
                        appliance_type=appliance.type,
                    )
                )

        if not smappee_base.smappee.local_polling:
            # presence value only available in cloud env
            entities.append(SmappeePresence(smappee_base, service_location))

    async_add_entities(entities, True)


class SmappeePresence(BinarySensorEntity):
    """Implementation of a Smappee presence binary sensor."""

    def __init__(self, smappee_base, service_location):
        """Initialize the Smappee sensor."""
        self._smappee_base = smappee_base
        self._service_location = service_location
        self._state = self._service_location.is_present

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return f"{self._service_location.service_location_name} - {PRESENCE_PREFIX}"

    @property
    def is_on(self):
        """Return if the binary sensor is turned on."""
        return self._state

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return BinarySensorDeviceClass.PRESENCE

    @property
    def unique_id(
        self,
    ):
        """Return the unique ID for this binary sensor."""
        return (
            f"{self._service_location.device_serial_number}-"
            f"{self._service_location.service_location_id}-"
            f"{BinarySensorDeviceClass.PRESENCE}"
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info for this binary sensor."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._service_location.device_serial_number)},
            manufacturer="Smappee",
            model=self._service_location.device_model,
            name=self._service_location.service_location_name,
            sw_version=self._service_location.firmware_version,
        )

    async def async_update(self):
        """Get the latest data from Smappee and update the state."""
        await self._smappee_base.async_update()

        self._state = self._service_location.is_present


class SmappeeAppliance(BinarySensorEntity):
    """Implementation of a Smappee binary sensor."""

    def __init__(
        self,
        smappee_base,
        service_location,
        appliance_id,
        appliance_name,
        appliance_type,
    ):
        """Initialize the Smappee sensor."""
        self._smappee_base = smappee_base
        self._service_location = service_location
        self._appliance_id = appliance_id
        self._appliance_name = appliance_name
        self._appliance_type = appliance_type
        self._state = False

    @property
    def name(self):
        """Return the name of the sensor."""
        return (
            f"{self._service_location.service_location_name} - "
            f"{BINARY_SENSOR_PREFIX} - "
            f"{self._appliance_name if self._appliance_name != '' else self._appliance_type}"
        )

    @property
    def is_on(self):
        """Return if the binary sensor is turned on."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend."""
        icon_mapping = {
            "Car Charger": "mdi:car",
            "Coffeemaker": "mdi:coffee",
            "Clothes Dryer": "mdi:tumble-dryer",
            "Clothes Iron": "mdi:hanger",
            "Dishwasher": "mdi:dishwasher",
            "Lights": "mdi:lightbulb",
            "Fan": "mdi:fan",
            "Freezer": "mdi:fridge",
            "Microwave": "mdi:microwave",
            "Oven": "mdi:stove",
            "Refrigerator": "mdi:fridge",
            "Stove": "mdi:stove",
            "Washing Machine": "mdi:washing-machine",
            "Water Pump": "mdi:water-pump",
        }
        return icon_mapping.get(self._appliance_type)

    @property
    def unique_id(
        self,
    ):
        """Return the unique ID for this binary sensor."""
        return (
            f"{self._service_location.device_serial_number}-"
            f"{self._service_location.service_location_id}-"
            f"appliance-{self._appliance_id}"
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info for this binary sensor."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._service_location.device_serial_number)},
            manufacturer="Smappee",
            model=self._service_location.device_model,
            name=self._service_location.service_location_name,
            sw_version=self._service_location.firmware_version,
        )

    async def async_update(self):
        """Get the latest data from Smappee and update the state."""
        await self._smappee_base.async_update()

        appliance = self._service_location.appliances.get(self._appliance_id)
        self._state = bool(appliance.state)
