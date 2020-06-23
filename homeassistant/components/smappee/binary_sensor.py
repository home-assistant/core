"""Support for monitoring a Smappee appliance binary sensor."""
import logging

from homeassistant.components.binary_sensor import (
    STATE_OFF,
    STATE_ON,
    BinarySensorEntity,
)

from .const import BASE, DOMAIN

_LOGGER = logging.getLogger(__name__)

BINARY_SENSOR_PREFIX = "Appliance"
PRESENCE_PREFIX = "Presence"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Smappee binary sensor."""
    smappee_base = hass.data[DOMAIN][BASE]

    entities = []
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
    def icon(self):
        """Icon to use in the frontend."""
        return "mdi:motion-sensor"

    @property
    def unique_id(self,):
        """Return the unique ID for this binary sensor."""
        return (
            f"{self._service_location.device_serial_number}-"
            f"{self._service_location.service_location_id}-"
            f"presence"
        )

    @property
    def device_info(self):
        """Return the device info for this binary sensor."""
        return {
            "identifiers": {(DOMAIN, self._service_location.device_serial_number)},
            "name": self._service_location.service_location_name,
            "manufacturer": "Smappee",
            "model": self._service_location.device_model,
            "sw_version": self._service_location.firmware_version,
            "via_device": (DOMAIN, self._smappee_base.smappee.username),
        }

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
        self._state = STATE_OFF
        self._appliance_power = None

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
        return self._state == STATE_ON

    @property
    def icon(self):
        """Icon to use in the frontend."""
        icon_mapping = {
            "Freezer": "mdi:fridge",
            "Refrigerator": "mdi:fridge",
            "Coffeemaker": "mdi:coffee",
            "Washing Machine": "mdi:washing-machine",
            "Clothes Dryer": "mdi:tumble-dryer",
            "Dishwasher": "mdi:dishwasher",
            "Clothes Iron": "mdi:hanger",
            "Stove": "mdi:stove",
            "Oven": "mdi:stove",
            "Microwave": "mdi:microwave",
            "Fan": "mdi:fan",
            "Car Charger": "mdi:car",
            "Water Pump": "mdi:water-pump",
        }
        return (
            icon_mapping.get(self._appliance_type)
            if self._appliance_type in icon_mapping
            else "mdi:power-plug"
        )

    @property
    def unique_id(self,):
        """Return the unique ID for this binary sensor."""
        return (
            f"{self._service_location.device_serial_number}-"
            f"{self._service_location.service_location_id}-"
            f"appliance-{self._appliance_id}"
        )

    @property
    def device_info(self):
        """Return the device info for this binary sensor."""
        return {
            "identifiers": {(DOMAIN, self._service_location.device_serial_number)},
            "name": self._service_location.service_location_name,
            "manufacturer": "Smappee",
            "model": self._service_location.device_model,
            "sw_version": self._service_location.firmware_version,
            "via_device": (DOMAIN, self._smappee_base.smappee.username),
        }

    def set_state(self, power):
        """Decides the binary sensor state based on power value."""
        self._state = STATE_ON if power > 0 else STATE_OFF

    async def async_update(self):
        """Get the latest data from Smappee and update the state."""
        await self._smappee_base.async_update()

        appliance = self._service_location.appliances.get(self._appliance_id)
        self._state = appliance.state
        self._appliance_power = appliance.power
