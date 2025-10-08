"""Support for monitoring a Smappee appliance binary sensor."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SmappeeConfigEntry
from .const import DOMAIN

BINARY_SENSOR_PREFIX = "Appliance"
PRESENCE_PREFIX = "Presence"

ICON_MAPPING = {
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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SmappeeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Smappee binary sensor."""
    smappee_base = config_entry.runtime_data

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

    _attr_device_class = BinarySensorDeviceClass.PRESENCE

    def __init__(self, smappee_base, service_location):
        """Initialize the Smappee sensor."""
        self._smappee_base = smappee_base
        self._service_location = service_location
        self._attr_name = (
            f"{service_location.service_location_name} - {PRESENCE_PREFIX}"
        )
        self._attr_unique_id = (
            f"{service_location.device_serial_number}-"
            f"{service_location.service_location_id}-"
            f"{BinarySensorDeviceClass.PRESENCE}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, service_location.device_serial_number)},
            manufacturer="Smappee",
            model=service_location.device_model,
            name=service_location.service_location_name,
            sw_version=service_location.firmware_version,
        )

    async def async_update(self) -> None:
        """Get the latest data from Smappee and update the state."""
        await self._smappee_base.async_update()

        self._attr_is_on = self._service_location.is_present


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
        self._attr_name = (
            f"{service_location.service_location_name} - "
            f"{BINARY_SENSOR_PREFIX} - "
            f"{appliance_name if appliance_name != '' else appliance_type}"
        )
        self._attr_unique_id = (
            f"{service_location.device_serial_number}-"
            f"{service_location.service_location_id}-"
            f"appliance-{appliance_id}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, service_location.device_serial_number)},
            manufacturer="Smappee",
            model=service_location.device_model,
            name=service_location.service_location_name,
            sw_version=service_location.firmware_version,
        )
        self._attr_icon = ICON_MAPPING.get(appliance_type)

    async def async_update(self) -> None:
        """Get the latest data from Smappee and update the state."""
        await self._smappee_base.async_update()

        appliance = self._service_location.appliances.get(self._appliance_id)
        self._attr_is_on = bool(appliance.state)
