"""Constants for the Renson Healthbox integration."""
from datetime import timedelta
from decimal import Decimal
from logging import Logger, getLogger

import voluptuous as vol

from homeassistant.const import Platform
from homeassistant.helpers import config_validation as cv

LOGGER: Logger = getLogger(__package__)

NAME = "Healthbox "
DOMAIN = "healthbox"
VERSION = "0.0.1"
MANUFACTURER = "Renson"
ATTRIBUTION = ""
SCAN_INTERVAL = timedelta(seconds=5)

PLATFORMS = [Platform.SENSOR]

SERVICE_START_ROOM_BOOST = "start_room_boost"
SERVICE_START_ROOM_BOOST_SCHEMA = vol.Schema(
    {
        vol.Required(cv.CONF_DEVICE_ID): cv.string,
        vol.Required("boost_level"): vol.All(int, vol.Range(min=10, max=200)),
        vol.Required("boost_timeout"): vol.All(int, vol.Range(min=5, max=240)),
    }
)

SERVICE_STOP_ROOM_BOOST = "stop_room_boost"
SERVICE_STOP_ROOM_BOOST_SCHEMA = vol.Schema(
    {vol.Required("device_id"): cv.string},
)

ALL_SERVICES = [SERVICE_START_ROOM_BOOST, SERVICE_STOP_ROOM_BOOST]


class HealthboxRoomBoost:
    """Healthbox  Room Boost object."""

    level: float
    enabled: bool
    remaining: int

    def __init__(
        self, level: float = 100, enabled: bool = False, remaining: int = 900
    ) -> None:
        """Initialize the HB Room Boost."""
        self.level = level
        self.enabled = enabled
        self.remaining = remaining


class HealthboxRoom:
    """Healthbox  Room object."""

    boost: HealthboxRoomBoost = None

    def __init__(self, room_id: int, room_data: object) -> None:
        """Initialize the HB Room."""
        self.room_id: int = room_id
        self.name: str = room_data["name"]
        self.type: str = room_data["type"]
        self.sensors_data: list = room_data["sensor"]
        self.room_type: str = room_data["type"]

    @property
    def indoor_temperature(self) -> Decimal:
        """HB Indoor Temperature."""
        return [
            sensor["parameter"]["temperature"]["value"]
            for sensor in self.sensors_data
            if "temperature" in sensor["parameter"]
        ][0]

    @property
    def indoor_humidity(self) -> Decimal:
        """HB Indoor Humidity."""
        return [
            sensor["parameter"]["humidity"]["value"]
            for sensor in self.sensors_data
            if "humidity" in sensor["parameter"]
        ][0]

    @property
    def indoor_co2_concentration(self) -> Decimal | None:
        """HB Indoor CO2 Concentration."""
        co2_concentration = None
        try:
            co2_concentration = [
                sensor["parameter"]["concentration"]["value"]
                for sensor in self.sensors_data
                if "concentration" in sensor["parameter"]
            ][0]
        except IndexError:
            co2_concentration = None
        return co2_concentration

    @property
    def indoor_aqi(self) -> Decimal | None:
        """HB Indoor Air Quality Index."""
        aqi = None
        try:
            aqi = [
                sensor["parameter"]["index"]["value"]
                for sensor in self.sensors_data
                if "index" in sensor["parameter"]
            ][0]
        except IndexError:
            aqi = None
        return aqi


class HealthboxDataObject:
    """Healthbox Data Object."""

    serial: str
    description: str
    warranty_number: str

    global_aqi: float = None

    rooms: list[HealthboxRoom]

    def __init__(self, data: any) -> None:
        """Initialize."""
        self.serial = data["serial"]
        self.description = data["description"]
        self.warranty_number = data["warranty_number"]

        self.global_aqi = self._get_global_aqi_from_data(data)

        hb_rooms: list[HealthboxRoom] = []
        for room in data["room"]:
            hb_room = HealthboxRoom(room, data["room"][room])
            hb_rooms.append(hb_room)

        self.rooms = hb_rooms

    def _get_global_aqi_from_data(self, data: any) -> float | None:
        """Set Global AQI from Data Object."""
        sensors = data["sensor"]
        for sensor in sensors:
            if sensor["type"] == "global air quality index":
                return sensor["parameter"]["index"]["value"]
        return None
