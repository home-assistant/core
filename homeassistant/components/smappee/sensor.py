"""Support for monitoring a Smappee energy sensor."""
from homeassistant.const import DEVICE_CLASS_POWER, ENERGY_WATT_HOUR, POWER_WATT, VOLT
from homeassistant.helpers.entity import Entity

from .const import DOMAIN

TREND_SENSORS = {
    "total_power": [
        "Total consumption - Active power",
        None,
        POWER_WATT,
        "total_power",
        DEVICE_CLASS_POWER,
        True,  # both cloud and local
    ],
    "alwayson": [
        "Always on - Active power",
        None,
        POWER_WATT,
        "alwayson",
        DEVICE_CLASS_POWER,
        False,  # cloud only
    ],
    "power_today": [
        "Total consumption - Today",
        "mdi:power-plug",
        ENERGY_WATT_HOUR,
        "power_today",
        None,
        False,  # cloud only
    ],
    "power_current_hour": [
        "Total consumption - Current hour",
        "mdi:power-plug",
        ENERGY_WATT_HOUR,
        "power_current_hour",
        None,
        False,  # cloud only
    ],
    "power_last_5_minutes": [
        "Total consumption - Last 5 minutes",
        "mdi:power-plug",
        ENERGY_WATT_HOUR,
        "power_last_5_minutes",
        None,
        False,  # cloud only
    ],
    "alwayson_today": [
        "Always on - Today",
        "mdi:sleep",
        ENERGY_WATT_HOUR,
        "alwayson_today",
        None,
        False,  # cloud only
    ],
}
REACTIVE_SENSORS = {
    "total_reactive_power": [
        "Total consumption - Reactive power",
        None,
        POWER_WATT,
        "total_reactive_power",
        DEVICE_CLASS_POWER,
    ]
}
SOLAR_SENSORS = {
    "solar_power": [
        "Total production - Active power",
        None,
        POWER_WATT,
        "solar_power",
        DEVICE_CLASS_POWER,
        True,  # both cloud and local
    ],
    "solar_today": [
        "Total production - Today",
        "mdi:white-balance-sunny",
        ENERGY_WATT_HOUR,
        "solar_today",
        None,
        False,  # cloud only
    ],
    "solar_current_hour": [
        "Total production - Current hour",
        "mdi:white-balance-sunny",
        ENERGY_WATT_HOUR,
        "solar_current_hour",
        None,
        False,  # cloud only
    ],
}
VOLTAGE_SENSORS = {
    "phase_voltages_a": [
        "Phase voltages - A",
        "mdi:flash",
        VOLT,
        "phase_voltage_a",
        None,
        ["ONE", "TWO", "THREE_STAR", "THREE_DELTA"],
    ],
    "phase_voltages_b": [
        "Phase voltages - B",
        "mdi:flash",
        VOLT,
        "phase_voltage_b",
        None,
        ["TWO", "THREE_STAR", "THREE_DELTA"],
    ],
    "phase_voltages_c": [
        "Phase voltages - C",
        "mdi:flash",
        VOLT,
        "phase_voltage_c",
        None,
        ["THREE_STAR"],
    ],
    "line_voltages_a": [
        "Line voltages - A",
        "mdi:flash",
        VOLT,
        "line_voltage_a",
        None,
        ["ONE", "TWO", "THREE_STAR", "THREE_DELTA"],
    ],
    "line_voltages_b": [
        "Line voltages - B",
        "mdi:flash",
        VOLT,
        "line_voltage_b",
        None,
        ["TWO", "THREE_STAR", "THREE_DELTA"],
    ],
    "line_voltages_c": [
        "Line voltages - C",
        "mdi:flash",
        VOLT,
        "line_voltage_c",
        None,
        ["THREE_STAR", "THREE_DELTA"],
    ],
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Smappee sensor."""
    smappee_base = hass.data[DOMAIN][config_entry.entry_id]

    entities = []
    for service_location in smappee_base.smappee.service_locations.values():
        # Add all basic sensors (realtime values and aggregators)
        # Some are available in local only env
        for sensor in TREND_SENSORS:
            if not service_location.local_polling or TREND_SENSORS[sensor][5]:
                entities.append(
                    SmappeeSensor(
                        smappee_base=smappee_base,
                        service_location=service_location,
                        sensor=sensor,
                        attributes=TREND_SENSORS[sensor],
                    )
                )

        if service_location.has_reactive_value:
            for reactive_sensor in REACTIVE_SENSORS:
                entities.append(
                    SmappeeSensor(
                        smappee_base=smappee_base,
                        service_location=service_location,
                        sensor=reactive_sensor,
                        attributes=REACTIVE_SENSORS[reactive_sensor],
                    )
                )

        # Add solar sensors (some are available in local only env)
        if service_location.has_solar_production:
            for sensor in SOLAR_SENSORS:
                if not service_location.local_polling or SOLAR_SENSORS[sensor][5]:
                    entities.append(
                        SmappeeSensor(
                            smappee_base=smappee_base,
                            service_location=service_location,
                            sensor=sensor,
                            attributes=SOLAR_SENSORS[sensor],
                        )
                    )

        # Add all CT measurements
        for measurement_id, measurement in service_location.measurements.items():
            entities.append(
                SmappeeSensor(
                    smappee_base=smappee_base,
                    service_location=service_location,
                    sensor="load",
                    attributes=[
                        measurement.name,
                        None,
                        POWER_WATT,
                        measurement_id,
                        DEVICE_CLASS_POWER,
                    ],
                )
            )

        # Add phase- and line voltages if available
        if service_location.has_voltage_values:
            for sensor_name, sensor in VOLTAGE_SENSORS.items():
                if service_location.phase_type in sensor[5]:
                    entities.append(
                        SmappeeSensor(
                            smappee_base=smappee_base,
                            service_location=service_location,
                            sensor=sensor_name,
                            attributes=sensor,
                        )
                    )

        # Add Gas and Water sensors
        for sensor_id, sensor in service_location.sensors.items():
            for channel in sensor.channels:
                gw_icon = "mdi:gas-cylinder"
                if channel.get("type") == "water":
                    gw_icon = "mdi:water"

                entities.append(
                    SmappeeSensor(
                        smappee_base=smappee_base,
                        service_location=service_location,
                        sensor="sensor",
                        attributes=[
                            channel.get("name"),
                            gw_icon,
                            channel.get("uom"),
                            f"{sensor_id}-{channel.get('channel')}",
                            None,
                        ],
                    )
                )

    async_add_entities(entities, True)


class SmappeeSensor(Entity):
    """Implementation of a Smappee sensor."""

    def __init__(self, smappee_base, service_location, sensor, attributes):
        """Initialize the Smappee sensor."""
        self._smappee_base = smappee_base
        self._service_location = service_location
        self._sensor = sensor
        self.data = None
        self._state = None
        self._name = attributes[0]
        self._icon = attributes[1]
        self._unit_of_measurement = attributes[2]
        self._sensor_id = attributes[3]
        self._device_class = attributes[4]

    @property
    def name(self):
        """Return the name for this sensor."""
        if self._sensor in ["sensor", "load"]:
            return (
                f"{self._service_location.service_location_name} - "
                f"{self._sensor.title()} - {self._name}"
            )

        return f"{self._service_location.service_location_name} - {self._name}"

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._device_class

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def unique_id(
        self,
    ):
        """Return the unique ID for this sensor."""
        if self._sensor in ["load", "sensor"]:
            return (
                f"{self._service_location.device_serial_number}-"
                f"{self._service_location.service_location_id}-"
                f"{self._sensor}-{self._sensor_id}"
            )

        return (
            f"{self._service_location.device_serial_number}-"
            f"{self._service_location.service_location_id}-"
            f"{self._sensor}"
        )

    @property
    def device_info(self):
        """Return the device info for this sensor."""
        return {
            "identifiers": {(DOMAIN, self._service_location.device_serial_number)},
            "name": self._service_location.service_location_name,
            "manufacturer": "Smappee",
            "model": self._service_location.device_model,
            "sw_version": self._service_location.firmware_version,
        }

    async def async_update(self):
        """Get the latest data from Smappee and update the state."""
        await self._smappee_base.async_update()

        if self._sensor == "total_power":
            self._state = self._service_location.total_power
        elif self._sensor == "total_reactive_power":
            self._state = self._service_location.total_reactive_power
        elif self._sensor == "solar_power":
            self._state = self._service_location.solar_power
        elif self._sensor == "alwayson":
            self._state = self._service_location.alwayson
        elif self._sensor in [
            "phase_voltages_a",
            "phase_voltages_b",
            "phase_voltages_c",
        ]:
            phase_voltages = self._service_location.phase_voltages
            if phase_voltages is not None:
                if self._sensor == "phase_voltages_a":
                    self._state = phase_voltages[0]
                elif self._sensor == "phase_voltages_b":
                    self._state = phase_voltages[1]
                elif self._sensor == "phase_voltages_c":
                    self._state = phase_voltages[2]
        elif self._sensor in ["line_voltages_a", "line_voltages_b", "line_voltages_c"]:
            line_voltages = self._service_location.line_voltages
            if line_voltages is not None:
                if self._sensor == "line_voltages_a":
                    self._state = line_voltages[0]
                elif self._sensor == "line_voltages_b":
                    self._state = line_voltages[1]
                elif self._sensor == "line_voltages_c":
                    self._state = line_voltages[2]
        elif self._sensor in [
            "power_today",
            "power_current_hour",
            "power_last_5_minutes",
            "solar_today",
            "solar_current_hour",
            "alwayson_today",
        ]:
            trend_value = self._service_location.aggregated_values.get(self._sensor)
            self._state = round(trend_value) if trend_value is not None else None
        elif self._sensor == "load":
            self._state = self._service_location.measurements.get(
                self._sensor_id
            ).active_total
        elif self._sensor == "sensor":
            sensor_id, channel_id = self._sensor_id.split("-")
            sensor = self._service_location.sensors.get(int(sensor_id))
            for channel in sensor.channels:
                if channel.get("channel") == int(channel_id):
                    self._state = channel.get("value_today")
