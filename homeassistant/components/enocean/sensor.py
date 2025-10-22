"""Support for EnOcean sensors."""

from __future__ import annotations

from enocean.protocol.packet import Packet
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    RestoreSensor,
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ID,
    CONF_NAME,
    PERCENTAGE,
    STATE_CLOSED,
    STATE_OPEN,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .config_entry import EnOceanConfigEntry
from .config_flow import (
    CONF_ENOCEAN_DEVICE_ID,
    CONF_ENOCEAN_DEVICE_NAME,
    CONF_ENOCEAN_DEVICE_TYPE_ID,
    CONF_ENOCEAN_DEVICES,
)
from .const import LOGGER
from .enocean_device_type import EnOceanDeviceType
from .enocean_id import EnOceanID
from .entity import EnOceanEntity

CONF_MAX_TEMP = "max_temp"
CONF_MIN_TEMP = "min_temp"
CONF_RANGE_FROM = "range_from"
CONF_RANGE_TO = "range_to"

DEFAULT_NAME = ""

SENSOR_TYPE_HUMIDITY = "humidity"
SENSOR_TYPE_POWER = "powersensor"
SENSOR_TYPE_TEMPERATURE = "temperature"
SENSOR_TYPE_WINDOWHANDLE = "windowhandle"


SENSOR_DESC_TEMPERATURE = SensorEntityDescription(
    key=SENSOR_TYPE_TEMPERATURE,
    name="Temperature",
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    device_class=SensorDeviceClass.TEMPERATURE,
    state_class=SensorStateClass.MEASUREMENT,
)

SENSOR_DESC_HUMIDITY = SensorEntityDescription(
    key=SENSOR_TYPE_HUMIDITY,
    name="Humidity",
    native_unit_of_measurement=PERCENTAGE,
    device_class=SensorDeviceClass.HUMIDITY,
    state_class=SensorStateClass.MEASUREMENT,
)

SENSOR_DESC_POWER = SensorEntityDescription(
    key=SENSOR_TYPE_POWER,
    name="Power",
    native_unit_of_measurement=UnitOfPower.WATT,
    device_class=SensorDeviceClass.POWER,
    state_class=SensorStateClass.MEASUREMENT,
)

SENSOR_DESC_WINDOWHANDLE = SensorEntityDescription(
    key=SENSOR_TYPE_WINDOWHANDLE, name="WindowHandle", icon="mdi:window-open-variant"
)


PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ID): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_DEVICE_CLASS, default=SENSOR_TYPE_POWER): cv.string,
        vol.Optional(CONF_MAX_TEMP, default=40): vol.Coerce(int),
        vol.Optional(CONF_MIN_TEMP, default=0): vol.Coerce(int),
        vol.Optional(CONF_RANGE_FROM, default=255): cv.positive_int,
        vol.Optional(CONF_RANGE_TO, default=0): cv.positive_int,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnOceanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""
    devices = config_entry.options.get(CONF_ENOCEAN_DEVICES, [])

    for device in devices:
        # get config data
        device_id = EnOceanID(device[CONF_ENOCEAN_DEVICE_ID])
        device_name = device[CONF_ENOCEAN_DEVICE_NAME]
        device_type_id = device[CONF_ENOCEAN_DEVICE_TYPE_ID]
        device_type = EnOceanDeviceType.get_supported_device_types()[device_type_id]
        eep = device_type.eep
        eep_type = int(eep[6:8], 16)

        # temperature sensors (EEP A5-02)
        if eep[0:5] == "A5-02":
            min_temp, max_temp = _get_a5_02_min_max_temp(device_id.to_string(), eep)
            async_add_entities(
                [
                    EnOceanTemperatureSensor(
                        enocean_id=device_id,
                        dev_name=device_name,
                        gateway_id=config_entry.runtime_data.gateway.chip_id,
                        description=SENSOR_DESC_TEMPERATURE,
                        scale_min=min_temp,
                        scale_max=max_temp,
                        range_from=255,
                        range_to=0,
                        dev_type=device_type,
                        name=None,
                    )
                ]
            )
            continue

        # temperature and humidity sensors (A5-04-01 / A5-04-02)
        if eep[0:5] == "A5-04":
            if eep_type < 0x01 or eep_type > 0x02:
                LOGGER.warning(
                    "Unsupported sensor EEP %s - ignoring EnOcean device %s",
                    eep,
                    device_id.to_string(),
                )
                continue

            min_temp = 0
            max_temp = 40

            if eep_type == 0x02:
                min_temp = -20
                max_temp = 60

            async_add_entities(
                [
                    EnOceanTemperatureSensor(
                        enocean_id=device_id,
                        dev_name=device_name,
                        gateway_id=config_entry.runtime_data.gateway.chip_id,
                        description=SENSOR_DESC_TEMPERATURE,
                        scale_min=min_temp,
                        scale_max=max_temp,
                        range_from=0,
                        range_to=250,
                        dev_type=device_type,
                        name="Temperature",
                    ),
                    EnOceanHumiditySensor(
                        enocean_id=device_id,
                        dev_name=device_name,
                        gateway_id=config_entry.runtime_data.gateway.chip_id,
                        description=SENSOR_DESC_HUMIDITY,
                        dev_type=device_type,
                        name="Humidity",
                    ),
                ]
            )
            continue

        # room operating panels (EEP A5-10-01 to A5-10-14)
        if eep[0:5] == "A5-10":
            if eep_type < 0x01 or eep_type > 0x14:
                LOGGER.warning(
                    "Unsupported sensor EEP %s - ignoring EnOcean device %s",
                    eep,
                    device_id.to_string(),
                )
                continue

            if eep_type < 0x10:
                async_add_entities(
                    [
                        EnOceanTemperatureSensor(
                            enocean_id=device_id,
                            dev_name=device_name,
                            gateway_id=config_entry.runtime_data.gateway.chip_id,
                            description=SENSOR_DESC_TEMPERATURE,
                            scale_min=0,
                            scale_max=40,
                            range_from=255,
                            range_to=0,
                            dev_type=device_type,
                            name="Temperature",
                        )
                    ]
                )
            else:
                async_add_entities(
                    [
                        EnOceanTemperatureSensor(
                            enocean_id=device_id,
                            dev_name=device_name,
                            gateway_id=config_entry.runtime_data.gateway.chip_id,
                            description=SENSOR_DESC_TEMPERATURE,
                            scale_min=0,
                            scale_max=40,
                            range_from=0,
                            range_to=250,
                            dev_type=device_type,
                            name="Temperature",
                        ),
                        EnOceanHumiditySensor(
                            enocean_id=device_id,
                            dev_name=device_name,
                            gateway_id=config_entry.runtime_data.gateway.chip_id,
                            description=SENSOR_DESC_HUMIDITY,
                            dev_type=device_type,
                            name="Humidity",
                        ),
                    ]
                )

            continue

        # power sensors A5-12-01 Automated Meter Reading (AMR) - Electricity;
        # the Permundo PSC234 also sends A5-12-01 messages (but uses natively
        # D2-01-09); as there is not (yet) a way to define multiple EEPs per
        # EnOcean device, but this device was previously supported in this
        # combination, we manually accept this here
        if eep == "A5-12-01" or device_type_id == "Permundo_PSC234":
            async_add_entities(
                [
                    EnOceanPowerSensor(
                        enocean_id=device_id,
                        dev_name=device_name,
                        gateway_id=config_entry.runtime_data.gateway.chip_id,
                        description=SENSOR_DESC_POWER,
                        dev_type=device_type,
                        name="Power usage",
                    )
                ]
            )
            continue

        # battery powered actuator
        if eep == "A5-20-01":
            async_add_entities(
                [
                    EnOceanTemperatureSensor(
                        enocean_id=device_id,
                        dev_name=device_name,
                        gateway_id=config_entry.runtime_data.gateway.chip_id,
                        description=SENSOR_DESC_TEMPERATURE,
                        scale_min=0,
                        scale_max=40,
                        range_from=0,
                        range_to=255,
                        dev_type=device_type,
                        name="Temperature",
                    )
                ]
            )
            continue

        # window handle (EEP F6-10-00)
        if eep == "F6-10-00":
            async_add_entities(
                [
                    EnOceanWindowHandle(
                        enocean_id=device_id,
                        dev_name=device_name,
                        gateway_id=config_entry.runtime_data.gateway.chip_id,
                        description=SENSOR_DESC_WINDOWHANDLE,
                        dev_type=device_type,
                    )
                ]
            )
            continue


class EnOceanSensor(EnOceanEntity, RestoreSensor):
    """Representation of an EnOcean sensor device such as a power meter."""

    def __init__(
        self,
        enocean_id: EnOceanID,
        dev_name: str,
        description: SensorEntityDescription,
        gateway_id: EnOceanID,
        dev_type: EnOceanDeviceType = EnOceanDeviceType(),
        name: str | None = None,
    ) -> None:
        """Initialize the EnOcean sensor device."""
        super().__init__(
            enocean_id=enocean_id,
            device_name=dev_name,
            name=name,
            device_type=dev_type,
            gateway_id=gateway_id,
        )
        self.entity_description = description

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to hass."""
        # If not None, we got an initial value.
        await super().async_added_to_hass()
        if self._attr_native_value is not None:
            return

        if (sensor_data := await self.async_get_last_sensor_data()) is not None:
            self._attr_native_value = sensor_data.native_value

    def value_changed(self, packet: Packet) -> None:
        """Update the internal state of the sensor."""


class EnOceanPowerSensor(EnOceanSensor):
    """Representation of an EnOcean power sensor.

    EEPs (EnOcean Equipment Profiles):
    - A5-12-01 (Automated Meter Reading, Electricity)
    """

    def value_changed(self, packet: Packet) -> None:
        """Update the internal state of the sensor."""
        if packet.rorg != 0xA5:
            return
        packet.parse_eep(0x12, 0x01)
        if packet.parsed["DT"]["raw_value"] == 1:
            # this packet reports the current value
            raw_val = packet.parsed["MR"]["raw_value"]
            divisor = packet.parsed["DIV"]["raw_value"]
            self._attr_native_value = raw_val / (10**divisor)
            self.schedule_update_ha_state()


class EnOceanTemperatureSensor(EnOceanSensor):
    """Representation of an EnOcean temperature sensor device.

    EEPs (EnOcean Equipment Profiles):
    - A5-02-01 to A5-02-1B All 8 Bit Temperature Sensors of A5-02
    - A5-10-01 to A5-10-14 (Room Operating Panels)
    - A5-04-01 (Temp. and Humidity Sensor, Range 0°C to +40°C and 0% to 100%)
    - A5-04-02 (Temp. and Humidity Sensor, Range -20°C to +60°C and 0% to 100%)
    - A5-10-10 (Temp. and Humidity Sensor and Set Point)
    - A5-10-12 (Temp. and Humidity Sensor, Set Point and Occupancy Control)
    - 10 Bit Temp. Sensors are not supported (A5-02-20, A5-02-30)

    For the following EEPs the scales must be set to "0 to 250":
    - A5-04-01
    - A5-04-02
    - A5-10-10 to A5-10-14
    """

    def __init__(
        self,
        enocean_id: EnOceanID,
        gateway_id: EnOceanID,
        dev_name: str,
        description: SensorEntityDescription,
        *,
        scale_min: int,
        scale_max: int,
        range_from: int,
        range_to: int,
        dev_type: EnOceanDeviceType = EnOceanDeviceType(),
        name: str | None = None,
    ) -> None:
        """Initialize the EnOcean temperature sensor device."""
        super().__init__(
            enocean_id=enocean_id,
            dev_name=dev_name,
            name=name,
            description=description,
            dev_type=dev_type,
            gateway_id=gateway_id,
        )
        self._scale_min = scale_min
        self._scale_max = scale_max
        self.range_from = range_from
        self.range_to = range_to

    def value_changed(self, packet: Packet) -> None:
        """Update the internal state of the sensor."""
        if packet.data[0] != 0xA5:
            return
        temp_scale = self._scale_max - self._scale_min
        temp_range = self.range_to - self.range_from
        raw_val = packet.data[3]
        temperature = temp_scale / temp_range * (raw_val - self.range_from)
        temperature += self._scale_min
        self._attr_native_value = round(temperature, 1)
        self.schedule_update_ha_state()


class EnOceanHumiditySensor(EnOceanSensor):
    """Representation of an EnOcean humidity sensor device.

    EEPs (EnOcean Equipment Profiles):
    - A5-04-01 (Temp. and Humidity Sensor, Range 0°C to +40°C and 0% to 100%)
    - A5-04-02 (Temp. and Humidity Sensor, Range -20°C to +60°C and 0% to 100%)
    - A5-10-10 to A5-10-14 (Room Operating Panels)
    """

    def value_changed(self, packet: Packet) -> None:
        """Update the internal state of the sensor."""
        if packet.rorg != 0xA5:
            return
        humidity = packet.data[2] * 100 / 250
        self._attr_native_value = round(humidity, 1)
        self.schedule_update_ha_state()


class EnOceanWindowHandle(EnOceanSensor):
    """Representation of an EnOcean window handle device.

    EEPs (EnOcean Equipment Profiles):
    - F6-10-00 (Mechanical handle / Hoppe AG)
    """

    def value_changed(self, packet: Packet) -> None:
        """Update the internal state of the sensor."""
        action = (packet.data[1] & 0x70) >> 4

        if action == 0x07:
            self._attr_native_value = STATE_CLOSED
        if action in (0x04, 0x06):
            self._attr_native_value = STATE_OPEN
        if action == 0x05:
            self._attr_native_value = "tilt"

        self.schedule_update_ha_state()


def _get_a5_02_min_max_temp(device_id: str, eep: str) -> tuple[int, int]:
    """Determine the min and max temp for an A5-02-XX temperature sensor."""
    sensor_range_type = int(eep[6:8], 16)

    if sensor_range_type in range(0x01, 0x0B + 1):
        multiplier = sensor_range_type - 0x01
        min_temp = -40 + multiplier * 10
        max_temp = multiplier * 10
        return min_temp, max_temp

    if sensor_range_type in range(0x10, 0x1B + 1):
        multiplier = sensor_range_type - 0x10
        min_temp = -60 + multiplier * 10
        max_temp = 20 + multiplier * 10
        return min_temp, max_temp

    LOGGER.warning(
        "EnOcean device %s is an unsupported A5-02-XX temperature sensor with EEP %s; using default values (min_temp = 0, max_temp = 40)",
        device_id,
        eep,
    )
    return 0, 40
