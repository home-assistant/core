"""Representation of Z-Wave binary_sensors."""
from openzwavemqtt.const import CommandClass, ValueIndex, ValueType

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_HEAT,
    DEVICE_CLASS_LOCK,
    DEVICE_CLASS_MOISTURE,
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_PROBLEM,
    DEVICE_CLASS_SAFETY,
    DEVICE_CLASS_SMOKE,
    DEVICE_CLASS_SOUND,
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DATA_UNSUBSCRIBE, DOMAIN
from .entity import ZWaveDeviceEntity

NOTIFICATION_TYPE = "index"
NOTIFICATION_VALUES = "values"
NOTIFICATION_DEVICE_CLASS = "device_class"
NOTIFICATION_SENSOR_ENABLED = "enabled"
NOTIFICATION_OFF_VALUE = "off_value"

NOTIFICATION_VALUE_CLEAR = 0

# Translation from values in Notification CC to binary sensors
# https://github.com/OpenZWave/open-zwave/blob/master/config/NotificationCCTypes.xml
NOTIFICATION_SENSORS = [
    {
        # Index 1: Smoke Alarm - Value Id's 1 and 2
        # Assuming here that Value 1 and 2 are not present at the same time
        NOTIFICATION_TYPE: ValueIndex.NOTIFICATION_SMOKE_ALARM,
        NOTIFICATION_VALUES: [1, 2],
        NOTIFICATION_DEVICE_CLASS: DEVICE_CLASS_SMOKE,
    },
    {
        # Index 1: Smoke Alarm - All other Value Id's
        # Create as disabled sensors
        NOTIFICATION_TYPE: ValueIndex.NOTIFICATION_SMOKE_ALARM,
        NOTIFICATION_VALUES: [3, 4, 5, 6, 7, 8],
        NOTIFICATION_DEVICE_CLASS: DEVICE_CLASS_SMOKE,
        NOTIFICATION_SENSOR_ENABLED: False,
    },
    {
        # Index 2: Carbon Monoxide - Value Id's 1 and 2
        NOTIFICATION_TYPE: ValueIndex.NOTIFICATION_CARBON_MONOOXIDE,
        NOTIFICATION_VALUES: [1, 2],
        NOTIFICATION_DEVICE_CLASS: DEVICE_CLASS_GAS,
    },
    {
        # Index 2: Carbon Monoxide - All other Value Id's
        NOTIFICATION_TYPE: ValueIndex.NOTIFICATION_CARBON_MONOOXIDE,
        NOTIFICATION_VALUES: [4, 5, 7],
        NOTIFICATION_DEVICE_CLASS: DEVICE_CLASS_GAS,
        NOTIFICATION_SENSOR_ENABLED: False,
    },
    {
        # Index 3: Carbon Dioxide - Value Id's 1 and 2
        NOTIFICATION_TYPE: ValueIndex.NOTIFICATION_CARBON_DIOXIDE,
        NOTIFICATION_VALUES: [1, 2],
        NOTIFICATION_DEVICE_CLASS: DEVICE_CLASS_GAS,
    },
    {
        # Index 3: Carbon Dioxide - All other Value Id's
        NOTIFICATION_TYPE: ValueIndex.NOTIFICATION_CARBON_DIOXIDE,
        NOTIFICATION_VALUES: [4, 5, 7],
        NOTIFICATION_DEVICE_CLASS: DEVICE_CLASS_GAS,
        NOTIFICATION_SENSOR_ENABLED: False,
    },
    {
        # Index 4: Heat - Value Id's 1, 2, 5, 6 (heat/underheat)
        NOTIFICATION_TYPE: ValueIndex.NOTIFICATION_HEAT,
        NOTIFICATION_VALUES: [1, 2, 5, 6],
        NOTIFICATION_DEVICE_CLASS: DEVICE_CLASS_HEAT,
    },
    {
        # Index 4: Heat - All other Value Id's
        NOTIFICATION_TYPE: ValueIndex.NOTIFICATION_HEAT,
        NOTIFICATION_VALUES: [3, 4, 8, 10, 11],
        NOTIFICATION_DEVICE_CLASS: DEVICE_CLASS_HEAT,
        NOTIFICATION_SENSOR_ENABLED: False,
    },
    {
        # Index 5: Water - Value Id's 1, 2, 3, 4
        NOTIFICATION_TYPE: ValueIndex.NOTIFICATION_WATER,
        NOTIFICATION_VALUES: [1, 2, 3, 4],
        NOTIFICATION_DEVICE_CLASS: DEVICE_CLASS_MOISTURE,
    },
    {
        # Index 5: Water - All other Value Id's
        NOTIFICATION_TYPE: ValueIndex.NOTIFICATION_WATER,
        NOTIFICATION_VALUES: [5],
        NOTIFICATION_DEVICE_CLASS: DEVICE_CLASS_MOISTURE,
        NOTIFICATION_SENSOR_ENABLED: False,
    },
    {
        # Index 6: Access Control - Value Id's 1, 2, 3, 4 (Lock)
        NOTIFICATION_TYPE: ValueIndex.NOTIFICATION_ACCESS_CONTROL,
        NOTIFICATION_VALUES: [1, 2, 3, 4],
        NOTIFICATION_DEVICE_CLASS: DEVICE_CLASS_LOCK,
    },
    {
        # Index 6: Access Control - Value Id 22 (door/window open)
        NOTIFICATION_TYPE: ValueIndex.NOTIFICATION_ACCESS_CONTROL,
        NOTIFICATION_VALUES: [22],
        NOTIFICATION_DEVICE_CLASS: DEVICE_CLASS_DOOR,
        NOTIFICATION_OFF_VALUE: 23,
    },
    {
        # Index 7: Home Security - Value Id's 1, 2 (intrusion)
        # Assuming that value 1 and 2 are not present at the same time
        NOTIFICATION_TYPE: ValueIndex.NOTIFICATION_HOME_SECURITY,
        NOTIFICATION_VALUES: [1, 2],
        NOTIFICATION_DEVICE_CLASS: DEVICE_CLASS_SAFETY,
    },
    {
        # Index 7: Home Security - Value Id's 3, 4, 9 (tampering)
        NOTIFICATION_TYPE: ValueIndex.NOTIFICATION_HOME_SECURITY,
        NOTIFICATION_VALUES: [3, 4, 9],
        NOTIFICATION_DEVICE_CLASS: DEVICE_CLASS_SAFETY,
    },
    {
        # Index 7: Home Security - Value Id's 5, 6 (glass breakage)
        # Assuming that value 5 and 6 are not present at the same time
        NOTIFICATION_TYPE: ValueIndex.NOTIFICATION_HOME_SECURITY,
        NOTIFICATION_VALUES: [5, 6],
        NOTIFICATION_DEVICE_CLASS: DEVICE_CLASS_SAFETY,
    },
    {
        # Index 7: Home Security - Value Id's 7, 8 (motion)
        NOTIFICATION_TYPE: ValueIndex.NOTIFICATION_HOME_SECURITY,
        NOTIFICATION_VALUES: [7, 8],
        NOTIFICATION_DEVICE_CLASS: DEVICE_CLASS_MOTION,
    },
    {
        # Index 8: Power management - Values 1...9
        NOTIFICATION_TYPE: ValueIndex.NOTIFICATION_POWER_MANAGEMENT,
        NOTIFICATION_VALUES: [1, 2, 3, 4, 5, 6, 7, 8, 9],
        NOTIFICATION_DEVICE_CLASS: DEVICE_CLASS_POWER,
        NOTIFICATION_SENSOR_ENABLED: False,
    },
    {
        # Index 8: Power management - Values 10...15
        # Battery values (mutually exclusive)
        NOTIFICATION_TYPE: ValueIndex.NOTIFICATION_POWER_MANAGEMENT,
        NOTIFICATION_VALUES: [10, 11, 12, 13, 14, 15],
        NOTIFICATION_DEVICE_CLASS: DEVICE_CLASS_POWER,
        NOTIFICATION_SENSOR_ENABLED: False,
        NOTIFICATION_OFF_VALUE: None,
    },
    {
        # Index 9: System - Value Id's 1, 2, 6, 7
        NOTIFICATION_TYPE: ValueIndex.NOTIFICATION_SYSTEM,
        NOTIFICATION_VALUES: [1, 2, 6, 7],
        NOTIFICATION_DEVICE_CLASS: DEVICE_CLASS_PROBLEM,
        NOTIFICATION_SENSOR_ENABLED: False,
    },
    {
        # Index 10: Emergency - Value Id's 1, 2, 3
        NOTIFICATION_TYPE: ValueIndex.NOTIFICATION_EMERGENCY,
        NOTIFICATION_VALUES: [1, 2, 3],
        NOTIFICATION_DEVICE_CLASS: DEVICE_CLASS_PROBLEM,
    },
    {
        # Index 11: Clock - Value Id's 1, 2
        NOTIFICATION_TYPE: ValueIndex.NOTIFICATION_CLOCK,
        NOTIFICATION_VALUES: [1, 2],
        NOTIFICATION_DEVICE_CLASS: None,
        NOTIFICATION_SENSOR_ENABLED: False,
    },
    {
        # Index 12: Appliance - All Value Id's
        NOTIFICATION_TYPE: ValueIndex.NOTIFICATION_APPLIANCE,
        NOTIFICATION_VALUES: [
            1,
            2,
            3,
            4,
            5,
            6,
            7,
            8,
            9,
            10,
            11,
            12,
            13,
            14,
            15,
            16,
            17,
            18,
            19,
            20,
            21,
        ],
        NOTIFICATION_DEVICE_CLASS: None,
    },
    {
        # Index 13: Home Health - Value Id's 1,2,3,4,5
        NOTIFICATION_TYPE: ValueIndex.NOTIFICATION_APPLIANCE,
        NOTIFICATION_VALUES: [1, 2, 3, 4, 5],
        NOTIFICATION_DEVICE_CLASS: None,
    },
    {
        # Index 14: Siren
        NOTIFICATION_TYPE: ValueIndex.NOTIFICATION_SIREN,
        NOTIFICATION_VALUES: [1],
        NOTIFICATION_DEVICE_CLASS: DEVICE_CLASS_SOUND,
    },
    {
        # Index 15: Water valve
        # ignore non-boolean values
        NOTIFICATION_TYPE: ValueIndex.NOTIFICATION_WATER_VALVE,
        NOTIFICATION_VALUES: [3, 4],
        NOTIFICATION_DEVICE_CLASS: DEVICE_CLASS_PROBLEM,
    },
    {
        # Index 16: Weather
        NOTIFICATION_TYPE: ValueIndex.NOTIFICATION_WEATHER,
        NOTIFICATION_VALUES: [1, 2],
        NOTIFICATION_DEVICE_CLASS: DEVICE_CLASS_PROBLEM,
    },
    {
        # Index 17: Irrigation
        # ignore non-boolean values
        NOTIFICATION_TYPE: ValueIndex.NOTIFICATION_IRRIGATION,
        NOTIFICATION_VALUES: [1, 2, 3, 4, 5],
        NOTIFICATION_DEVICE_CLASS: None,
    },
    {
        # Index 18: Gas
        NOTIFICATION_TYPE: ValueIndex.NOTIFICATION_GAS,
        NOTIFICATION_VALUES: [1, 2, 3, 4],
        NOTIFICATION_DEVICE_CLASS: DEVICE_CLASS_GAS,
    },
    {
        # Index 18: Gas
        NOTIFICATION_TYPE: ValueIndex.NOTIFICATION_GAS,
        NOTIFICATION_VALUES: [6],
        NOTIFICATION_DEVICE_CLASS: DEVICE_CLASS_PROBLEM,
    },
]


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Z-Wave binary_sensor from config entry."""

    @callback
    def async_add_binary_sensor(values):
        """Add Z-Wave Binary Sensor(s)."""
        async_add_entities(VALUE_TYPE_SENSORS[values.primary.type](values))

    hass.data[DOMAIN][config_entry.entry_id][DATA_UNSUBSCRIBE].append(
        async_dispatcher_connect(
            hass, f"{DOMAIN}_new_{BINARY_SENSOR_DOMAIN}", async_add_binary_sensor
        )
    )


@callback
def async_get_legacy_binary_sensors(values):
    """Add Legacy/classic Z-Wave Binary Sensor."""
    return [ZWaveBinarySensor(values)]


@callback
def async_get_notification_sensors(values):
    """Convert Notification values into binary sensors."""
    sensors_to_add = []
    for list_value in values.primary.value["List"]:
        # check if we have a mapping for this value
        for item in NOTIFICATION_SENSORS:
            if item[NOTIFICATION_TYPE] != values.primary.index:
                continue
            if list_value["Value"] not in item[NOTIFICATION_VALUES]:
                continue
            sensors_to_add.append(
                ZWaveListValueSensor(
                    # required values
                    values,
                    list_value["Value"],
                    item[NOTIFICATION_DEVICE_CLASS],
                    # optional values
                    item.get(NOTIFICATION_SENSOR_ENABLED, True),
                    item.get(NOTIFICATION_OFF_VALUE, NOTIFICATION_VALUE_CLEAR),
                )
            )
    return sensors_to_add


VALUE_TYPE_SENSORS = {
    ValueType.BOOL: async_get_legacy_binary_sensors,
    ValueType.LIST: async_get_notification_sensors,
}


class ZWaveBinarySensor(ZWaveDeviceEntity, BinarySensorEntity):
    """Representation of a Z-Wave binary_sensor."""

    @property
    def is_on(self):
        """Return if the sensor is on or off."""
        return self.values.primary.value

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        # Legacy binary sensors are phased out (replaced by notification sensors)
        # Disable by default to not confuse users
        for item in self.values.primary.node.values():
            if item.command_class == CommandClass.NOTIFICATION:
                # This device properly implements the Notification CC, legacy sensor can be disabled
                return False
        return True


class ZWaveListValueSensor(ZWaveDeviceEntity, BinarySensorEntity):
    """Representation of a binary_sensor from values in the Z-Wave Notification CommandClass."""

    def __init__(
        self,
        values,
        on_value,
        device_class=None,
        default_enabled=True,
        off_value=NOTIFICATION_VALUE_CLEAR,
    ):
        """Initialize a ZWaveListValueSensor entity."""
        super().__init__(values)
        self._on_value = on_value
        self._device_class = device_class
        self._default_enabled = default_enabled
        self._off_value = off_value
        # make sure the correct value is selected at startup
        self._state = False
        self.on_value_update()

    @callback
    def on_value_update(self):
        """Call when a value is added/updated in the underlying EntityValues Collection."""
        if self.values.primary.value["Selected_id"] == self._on_value:
            # Only when the active ID exactly matches our watched ON value, set sensor state to ON
            self._state = True
        elif self.values.primary.value["Selected_id"] == self._off_value:
            # Only when the active ID exactly matches our watched OFF value, set sensor state to OFF
            self._state = False
        elif (
            self._off_value is None
            and self.values.primary.value["Selected_id"] != self._on_value
        ):
            # Off value not explicitly specified
            # Some values are reset by the simple fact they're overruled by another value coming in
            # For example the battery charging values in Power Management Index
            self._state = False

    @property
    def name(self):
        """Return the name of the entity."""
        # Append value label to base name
        base_name = super().name
        value_label = ""
        for item in self.values.primary.value["List"]:
            if item["Value"] == self._on_value:
                value_label = item["Label"]
                break
        # Strip "on location" / "at location" from name
        # Note: We're assuming that we don't retrieve 2 values with different location
        value_label = value_label.split(" on ")[0]
        value_label = value_label.split(" at ")[0]
        return f"{base_name}: {value_label}"

    @property
    def unique_id(self):
        """Return the unique_id of the entity."""
        unique_id = super().unique_id
        return f"{unique_id}.{self._on_value}"

    @property
    def is_on(self):
        """Return if the sensor is on or off."""
        return self._state

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._device_class

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        # We hide the more advanced sensors by default to not overwhelm users
        return self._default_enabled
