"""Provides a parser to convert raw AirTouch messages into Aircon objects."""

import logging

from .airtouch_aircon import Aircon
from .airtouch_sensor import Sensor
from .airtouch_zone import AirtouchZone
from .enums import AcMode, ZoneStatus
from .message_constants import MessageConstants

MIN_RESPONSE_LENGTH = MessageConstants.AIRTOUCH_ID_START


class MessageResponseParser:
    """Parses raw response buffers from AirTouch into higher-level objects."""

    def __init__(self, response_buffer: bytearray, log: logging.Logger) -> None:
        """Initialize a new MessageResponseParser.

        :param response_buffer: The raw bytes returned from the AirTouch system.
        :param log: A logging.Logger instance for debug information.
        """
        self.response_buffer = response_buffer
        self.log = log

    def _parse_sensor(self, byte_value: int) -> Sensor:
        """Parse a temperature sensor byte."""
        sensor = Sensor()
        sensor.current_temperature = byte_value & 0x3F
        sensor.is_available = bool(byte_value & 0x80)
        return sensor

    def parse(self) -> Aircon:
        """Parse the AirTouch response buffer to create and populate an Aircon object.

        :return: The populated Aircon instance.
        """
        if len(self.response_buffer) < MIN_RESPONSE_LENGTH:
            raise ValueError(
                f"AirTouch response was too short: {len(self.response_buffer)} bytes"
            )

        self.log.debug("Length of response: %d", len(self.response_buffer))

        ac_id = 0
        self.log.debug("AC id is: %d", ac_id)

        # Initialize Aircon with ac_id
        aircon = Aircon(ac_id=ac_id)

        # Running status
        aircon.status = bool(self.response_buffer[MessageConstants.AIRCON_STATUS] >> 7)
        self.log.debug("AC status is: %s", aircon.status)

        # Unit name (16 bytes from the buffer)
        unit_name = (
            bytes(
                self.response_buffer[
                    MessageConstants.SYSTEM_NAME_START : MessageConstants.SYSTEM_NAME_START
                    + 16
                ]
            )
            .decode("ascii", "ignore")
            .strip("\x00 ")
        )
        self.log.debug("Unit name is: '%s'", unit_name)

        # Desired temperature
        aircon.desired_temperature = (
            self.response_buffer[MessageConstants.DESIRED_TEMPERATURE] & 127
        )

        # AC Mode
        mode = self.response_buffer[MessageConstants.AIRCON_MODE] & 127
        aircon.mode = {
            0: AcMode.AUTO,
            1: AcMode.HEAT,
            2: AcMode.DRY,
            3: AcMode.FAN,
            4: AcMode.COOL,
        }.get(mode, AcMode.AUTO)

        aircon.brand_id = self.response_buffer[MessageConstants.AIRCON_BRAND_ID]
        self.log.debug("Air conditioner brand id is: %d", aircon.brand_id)

        # Fan speed
        aircon.fan_speed = self.response_buffer[MessageConstants.FAN_SPEED] & 15
        if aircon.fan_speed in (0, 4):
            aircon.fan_speed = 0
        self.log.debug("Fan speed is set to %d", aircon.fan_speed)

        # Sensors
        aircon.sensors = self.parse_sensors()
        # Zones
        aircon.zones = self.parse_zones(aircon)

        # Calculate average room temperature from available zone sensors
        room_temp: float = 0
        room_temp_zones = 0
        for zone in aircon.zones:
            if zone.sensor and zone.sensor.is_available:
                room_temp_zones += 1
                room_temp += zone.sensor.current_temperature
            else:
                self.log.debug("Zone %s doesn't have a sensor", zone)

        if room_temp_zones:
            aircon.room_temperature = room_temp / room_temp_zones
        else:
            aircon.room_temperature = 0
        self.log.debug("Room temperature is: %s", aircon.room_temperature)

        return aircon

    def parse_sensors(self) -> list[Sensor]:
        """Parse sensor information from the response buffer.

        :return: A list of Sensor objects.
        """
        sensors = []
        for i in range(32):
            byte_value = self.response_buffer[MessageConstants.SENSOR_DATA_START + i]
            sensor = self._parse_sensor(byte_value)
            self.log.debug("Sensor %d: %s", i, f"{byte_value & 0xFF:08b}")

            self.log.debug(
                "Sensor %d temp is %d, IsAvailable: %s",
                i,
                sensor.current_temperature,
                sensor.is_available,
            )
            sensors.append(sensor)

        return sensors

    def parse_zones(self, aircon: Aircon) -> list[AirtouchZone]:
        """Parse zone information from the response buffer and associate it with the given Aircon.

        :param aircon: The Aircon object to which parsed zones will be associated.
        :return: A list of AirtouchZone objects.
        """
        zone_data = bytearray(16)
        group_data = bytearray(16)
        group_names = bytearray(128)
        group_setting = bytearray(16)

        for i in range(16):
            zone_data[i] = self.response_buffer[MessageConstants.ZONE_DATA_START + i]
            group_data[i] = self.response_buffer[MessageConstants.GROUP_DATA_START + i]

        for i in range(128):
            group_names[i] = self.response_buffer[MessageConstants.GROUP_NAME_START + i]

        for i in range(16):
            group_setting[i] = self.response_buffer[
                MessageConstants.GROUP_SETTING_START + i
            ]

        zones = []
        num_zones = self.response_buffer[MessageConstants.NUMBER_OF_ZONES]
        if num_zones > 16:
            raise ValueError(f"AirTouch reported unsupported zone count: {num_zones}")
        self.log.debug("Number of zones: %d", num_zones)

        for i in range(num_zones):
            zone = AirtouchZone(0)
            # Attach a sensor if available
            if aircon.sensors[i].is_available:
                zone.sensor = aircon.sensors[i]

            # Zone name (8 bytes per zone)
            zone_name = (
                bytes(group_names[i * 8 : (i + 1) * 8])
                .decode("ascii", "ignore")
                .strip("\x00 ")
            )
            zone.name = zone_name or f"Zone {i + 1}"
            zone.id = i

            # Zone status
            start_zone = (group_data[i] & 240) >> 4
            zone.status = (
                ZoneStatus.ZONE_ON
                if ((zone_data[start_zone] + 256) & 128) >> 7
                else ZoneStatus.ZONE_OFF
            )
            self.log.debug(
                "Zone %d name is '%s' and status is: %s",
                i,
                zone.name,
                zone.status,
            )

            # Desired temperature
            zone.desired_temperature = (group_setting[i] & 31) + 1
            self.log.debug("Desired temperature: %d", zone.desired_temperature)

            zones.append(zone)

        touchpad_group_id = self.response_buffer[MessageConstants.TOUCHPAD_GROUP_ID]
        touchpad_sensor = self._parse_sensor(
            self.response_buffer[MessageConstants.TOUCHPAD_TEMPERATURE]
        )
        if 0 < touchpad_group_id <= num_zones and touchpad_sensor.is_available:
            zones[touchpad_group_id - 1].sensor = touchpad_sensor
            self.log.debug(
                "Assigned touchpad temperature %d to zone %d",
                touchpad_sensor.current_temperature,
                touchpad_group_id - 1,
            )

        return zones
