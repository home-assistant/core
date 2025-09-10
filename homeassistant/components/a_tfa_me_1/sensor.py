"""TFA.me station integration: sensor.py."""

from collections import deque
from datetime import datetime
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, StateType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_MAPPING, DOMAIN, ICON_MAPPING, TIMEOUT_MAPPING
from .coordinator import TFAmeDataCoordinator
from .text import TFAmeTextEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,  # TFAmeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TFA.me as Sensor."""

    # Get coordinator
    coordinator = entry.runtime_data
    # Initialize first refresh/request and wait for parsed JSON data from coordinator
    try:
        # await coordinator.async_config_entry_first_refresh()
        # Collect all entities (entities are part of device)
        sensors_start = []
        sensors_start_txt = []
        for entity_id in coordinator.data:
            sensor_id = coordinator.data[entity_id]["sensor_id"]
            if entity_id not in coordinator.sensor_entity_list:
                if "_txt" in entity_id:
                    sensors_start_txt.append(
                        TFAmeTextEntity(coordinator, sensor_id, entity_id)
                    )
                else:
                    sensors_start.append(
                        TFAmeSensorEntity(coordinator, sensor_id, entity_id)
                    )
                coordinator.sensor_entity_list.append(entity_id)

        # Add all entities
        async_add_entities(sensors_start, True)
        async_add_entities(sensors_start_txt, True)

    except Exception as error:
        raise ConfigEntryNotReady(
            f"Station not available: {error}"
        ) from error  # Catch errors here

    # Find new sensors in coordinator data
    async def async_discover_new_entities():
        """Find new sensors and register them."""
        coordinator = entry.runtime_data

        new_sensors = []
        new_sensors_txt = []
        for entity_id in coordinator.data:
            sensor_id = coordinator.data[entity_id]["sensor_id"]
            if entity_id not in coordinator.sensor_entity_list:
                if "_txt" in entity_id:
                    new_sensors_txt.append(
                        TFAmeTextEntity(coordinator, sensor_id, entity_id)
                    )
                else:
                    new_sensors.append(
                        TFAmeSensorEntity(coordinator, sensor_id, entity_id)
                    )
                coordinator.sensor_entity_list.append(entity_id)

        if new_sensors:
            async_add_entities(new_sensors)
        if new_sensors_txt:
            async_add_entities(new_sensors_txt)

    # Save function in Home Assistant so that it can be called as service
    hass.data[DOMAIN][
        entry.entry_id
    ].async_discover_new_entities = async_discover_new_entities


# ---- TFA.me sensor entity ----
class TFAmeSensorEntity(CoordinatorEntity, SensorEntity):
    """Represents in Home Assistant a single measurement of a sensor."""

    _attr_has_entity_name = True
    _attr_should_poll = True

    def __init__(
        self,
        coordinator: TFAmeDataCoordinator,
        sensor_id: str,
        entity_id: str,
    ) -> None:
        """Initialize sensor entity."""
        try:
            super().__init__(coordinator)
            self.coordinator = coordinator
            self.host = coordinator.host
            self.multiple_entities = coordinator.multiple_entities
            # self.gateway_id = gateway_id
            self.entity_id = entity_id
            self.gateway_id = self.coordinator.data[self.entity_id]["gateway_id"]

            self.sensor_id = sensor_id
            self._attr_icon = ""
            self._attr_unique_id = entity_id  # just the entity ID
            self._attr_name = entity_id  # just the entity ID
            ids_str = f"{sensor_id}_{self.gateway_id}"
            self._attr_device_info = {
                "identifiers": {
                    (
                        DOMAIN,
                        ids_str,
                    )  # this IDs are used to ground entities tom sensors
                },  # Unique ID for device/sensor
                "name": self.format_string_tfa_id(
                    self.sensor_id, self.gateway_id, self.multiple_entities
                ),  # 'TFA.me XXX-XXX-XXX'
                "manufacturer": "TFA/Dostmann",
                "model": self.format_string_tfa_type(
                    sensor_id
                ),  # 'Sensor/Station type XX'
                # "sw_version": "1.0",
                # "hw_version": "1.0",
                # "serial_number": "123"
            }
            # History
            self.rain_history: SensorHistory = SensorHistory(max_age_minutes=60)
            self.rain_history_24: SensorHistory = SensorHistory(
                max_age_minutes=(24 * 60)
            )

            # When this is a station add URL to station
            hex_value = int(sensor_id[:2], 16)
            if hex_value < 160:
                self._attr_device_info["configuration_url"] = (
                    f"http://{coordinator.host}/ha_menu"
                )

            # Add icon for measurement
            self.measure_name = self.coordinator.data[self.entity_id]["measurement"]
            self.init_measure_value = self.coordinator.data[self.entity_id]["value"]

            self._attr_icon = self.get_icon(
                self.measure_name, float(self.init_measure_value)
            )

        except (ValueError, TypeError, KeyError):
            return

    # ---- Called when coordinator has new data, used to update rain histories ----
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        if "rain_hour" in self.entity_id:
            try:
                value = self.coordinator.data[self.entity_id]["value"]
                ts = self.coordinator.data[self.entity_id]["ts"]
                self.rain_history.add_measurement(value, ts)

            except (ValueError, TypeError, KeyError):
                value = 0

        if "rain_24hours" in self.entity_id:
            try:
                value = self.coordinator.data[self.entity_id]["value"]
                ts = self.coordinator.data[self.entity_id]["ts"]
                self.rain_history_24.add_measurement(value, ts)

            except (ValueError, TypeError, KeyError):
                value = 0

        # Update state in HA
        super()._handle_coordinator_update()

    # ---- String helper for sensor names ----
    def format_string_tfa_id(self, s: str, gw_id: str, multiple_entities: bool):
        """Convert string 'xxxxxxxxx' into 'TFA.me XXX-XXX-XXX'."""
        if multiple_entities:
            return f"TFA.me {s[:3].upper()}-{s[3:6].upper()}-{s[6:].upper()}({gw_id.upper()})"
        # else:
        return f"TFA.me {s[:3].upper()}-{s[3:6].upper()}-{s[6:].upper()}"

    # ---- String helper for sensor/station types ----
    def format_string_tfa_type(self, s: str):
        """Convert string 'xxxxxxxxx' into 'Sensor/station type XX'."""

        type_id: str = (s[:2]).upper()
        info_str: str = "?"
        try:
            info_str = DEVICE_MAPPING[type_id]
        except KeyError:
            info_str = "?"
        return info_str

    # ---- Property: Unique entity ID ----
    # "sensor.id_measurement" e.g. "sensor.a12345678_temperature"
    @property
    def unique_id(self) -> str:
        """Unique entity ID for Home Assistant."""
        return f"tfame_{self.entity_id}"

    # ---- Property: Name of sensor entity in HA: "ID MEASUEREMENT",  e.g. "A01234456 Temperature" ----
    @property
    def name(self) -> str:
        """Name of sensors in Home Assistant."""
        try:
            sensor_data = self.coordinator.data[self.entity_id]
            str1 = f"{sensor_data['sensor_name']} {sensor_data['measurement'].capitalize()}"
            str2 = str1.replace("Rssi", "RSSI")
            str3 = str2.replace("Co2", "CO2")
            return str3.replace("_", " ")
        except (ValueError, TypeError, KeyError):
            return "None"

    # ---- Property: Name of measurement value in HA: "measurement", e.g. "temperature" ----
    @property
    def measurement_name(self):
        """Name of measurement."""
        try:
            measurement_name = self.coordinator.data[self.entity_id]["measurement"]
        except (ValueError, TypeError, KeyError):
            return None

        return measurement_name

    # ---- Property: measurement value of an entity itself ----
    @property
    def native_value(self) -> StateType:  # None | int | float | str | StateType:
        """Actual measurement value."""
        try:
            # Is measurement value still valid or old
            last_update_ts: int = int(self.coordinator.data[self.entity_id]["ts"])
            utc_now = datetime.now()
            utc_now_ts = int(utc_now.timestamp())
            timeout = self.get_timeout(self.sensor_id)
            if (utc_now_ts - last_update_ts) <= (timeout):
                measurement_value = self.coordinator.data[self.entity_id]["value"]

                # Is this rain sensor relative values
                if "rain_rel" in self.entity_id:
                    reset_rain = self.coordinator.data[self.entity_id]["reset_rain"]
                    if reset_rain:
                        self.init_measure_value = measurement_value
                        self.coordinator.data[self.entity_id]["reset_rain"] = False

                    measurement_value = float(
                        float(measurement_value) - float(self.init_measure_value)
                    )
                    measurement_value = round(measurement_value, 1)

                # Is this rain sensor last hour
                if "rain_hour" in self.entity_id:
                    # try:
                    measurement_value = float(0)
                    # str_rain = self.entity_id
                    # value = self.coordinator.data[str_rain]["value"]
                    if len(self.rain_history.data) >= 2:
                        oldest, newest = self.rain_history.get_oldest_and_newest()
                        measurement_value = float(newest[0]) - float(oldest[0])
                        measurement_value = round(measurement_value, 1)
                    # except Exception as error:
                    #    msg2: str = (
                    #        "Exception requesting data: str_rain = '"
                    #        + self.entity_id
                    #        + "' "
                    #        + str(error.__doc__)
                    #    )
                    #    _LOGGER.error(msg2)
                    #    measurement_value = float(0)
                    #    measurement_value = round(measurement_value, 1)
                    #    raise

                # Is this rain sensor last 24 hours
                if "rain_24hours" in self.entity_id:
                    measurement_value = float(0)
                    if len(self.rain_history_24.data) >= 2:
                        oldest, newest = self.rain_history_24.get_oldest_and_newest()
                        measurement_value = float(newest[0]) - float(oldest[0])
                        measurement_value = round(measurement_value, 1)

                # Is this wind sensor, add degrees entity
                if "wind_direction_deg" in self.entity_id:
                    try:
                        str_wind_deg = self.entity_id
                        str_wind_deg = str_wind_deg.replace("_deg", "")
                        value = self.coordinator.data[str_wind_deg]["value"]
                        measurement_value = float(0)
                        measurement_value = float(value) * (360 / 16)
                    except Exception as error:
                        msg_wind_deg: str = (
                            "Exception requesting data: str_wind_deg = '"
                            + str_wind_deg
                            + "' "
                            + str(error.__doc__)
                        )
                        _LOGGER.error(msg_wind_deg)
                        measurement_value = float(0)
                        measurement_value = round(measurement_value, 1)
                        raise

            else:
                measurement_value = None  # STATE_UNAVAILABLE  #   None  # TO.DO insert again or use other value STATE_UNAVAILABLE

        except (ValueError, TypeError, KeyError):
            return None  # Wrong data, Home Assistant shows sensor as "unavailable"

        return measurement_value

    # ---- Property: Unit of measurement value, e.g. for wind speed unit is "m/s" ----
    @property
    def native_unit_of_measurement(self) -> str | None:
        """Unit of measurement value."""
        try:
            unit = self.coordinator.data[self.entity_id]["unit"]
            if unit is None:
                return None  # Home Assistant shows "unavailable"
            return str(unit)
        except (ValueError, TypeError, KeyError):
            return ""

    # ---- Property: Extra attributes dictionary for an entity ----
    # "sensor_name": Sensor ID, e.g. "A01234456"
    # "measurement": Name of measurement value, e.g. "temperature"
    # "timestamp"  : UTC timestamp, e.g. "2025-03-06T08:46:01Z"
    # "icon"       : Icon for a measurement value, e.g. "mdi:water-percent"
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Additional attributes."""

        try:
            sensor_data = self.coordinator.data[self.entity_id]
            return {
                "sensor_name": sensor_data["sensor_name"],
                "measurement": sensor_data["measurement"],
                "timestamp": sensor_data["timestamp"],
                "icon": self._attr_icon,
            }
        except (ValueError, TypeError, KeyError):
            return {}

    # ---- Property: Icon for a measurement value ----
    @property
    def icon(self) -> str:
        """Returns icon based on actual measurement value."""
        value = self.native_value
        # get the icon
        return self.get_icon(self.measurement_name, value)

    # ---- Get an icon for measurement type based on measurement value (see MDI list) ----
    def get_icon(self, measurement_type, value_state):
        """Return icon for a sensor type."""

        if value_state is None:
            value = value_state  # use None
        else:
            try:
                value = float(value_state)
            except (ValueError, TypeError, KeyError):
                value = 0

        # Temperature & temperatue probe
        if (measurement_type == "temperature") | (
            measurement_type == "temperature_probe"
        ):
            if value is None:
                return ICON_MAPPING["temperature"]["default"]
            if value >= 25:
                return ICON_MAPPING["temperature"]["high"]
            if value <= 0:
                return ICON_MAPPING["temperature"]["low"]
            return ICON_MAPPING["temperature"]["default"]

        # Humidity
        if measurement_type == "humidity":
            if value is None:
                return ICON_MAPPING["humidity"]["default"]
            if (value >= 65) | (value <= 30):
                return ICON_MAPPING["humidity"]["alert"]
            return ICON_MAPPING["humidity"]["default"]

        # Air quality CO2
        if measurement_type == "co2":
            return ICON_MAPPING["co2"]["default"]

        # Barometric pressure
        if measurement_type == "barometric_pressure":
            return ICON_MAPPING["barometric_pressure"]["default"]

        # RSSI value for 868 MHz reception: range 0...255
        if measurement_type == "rssi":
            if value is None:
                return ICON_MAPPING["rssi"]["weak"]

            if value < 100:
                return ICON_MAPPING["rssi"]["weak"]
            if value < 150:
                return ICON_MAPPING["rssi"]["middle"]
            if value < 220:
                return ICON_MAPPING["rssi"]["good"]
            return ICON_MAPPING["rssi"]["strong"]

        # Battery: 0 = low battery, 1 = good battery
        if measurement_type == "lowbatt":
            return (
                ICON_MAPPING["lowbatt"]["low"]
                if value == 1
                else ICON_MAPPING["lowbatt"]["full"]
            )

        # Wind direction, speed & gust
        if measurement_type == "wind_direction_deg":
            return self.get_wind_direction_icon(value / (360 / 16))
        if measurement_type == "wind_direction":
            return self.get_wind_direction_icon(value)
        if measurement_type == "wind_gust":
            return ICON_MAPPING["wind"]["wind"]
        if measurement_type == "wind_speed":
            return ICON_MAPPING["wind"]["gust"]

        # Rain:
        if measurement_type == "rain":
            return ICON_MAPPING["rain"]["moderate"]

        if (
            (measurement_type == "rain_relative")
            | (measurement_type == "rain_1_hour")
            | (measurement_type == "rain_24_hours")
        ):
            return self.get_rain_icon(value)

        # Unknown measurement type
        return "mdi:help-circle"  # Fallback-Icon

    # ---- Get an icon for rain ----
    def get_rain_icon(self, value):
        """Return icon for rain based on value."""
        if value is None:
            return "mdi:help-circle"
        if value < 0.1:
            return ICON_MAPPING["rain"]["none"]
        if 0.1 <= value < 0.5:
            return ICON_MAPPING["rain"]["light"]
        if 0.5 <= value < 4:
            return ICON_MAPPING["rain"]["moderate"]
        # if value >= 4:
        return ICON_MAPPING["rain"]["heavy"]

    # ---- Get an icon for wind direction based on values (0...15) ----
    # Remark: there are only 8 arrows for direction but 16 wind direction so icon does not match optimal
    def get_wind_direction_icon(self, value):
        """Return icon for wind direction based on value 0 to 15."""
        if value is None:
            return "mdi:compass-outline"

        if 0 <= value <= 1:
            return "mdi:arrow-down"  # N (North)
        if 2 <= value <= 3:
            return "mdi:arrow-bottom-left"  # NE (North-East)
        if 4 <= value <= 5:
            return "mdi:arrow-left"  # E (East)
        if 6 <= value <= 7:
            return "mdi:arrow-top-left"  # SE (South-East)
        if 8 <= value <= 9:
            return "mdi:arrow-up"  # S (South)
        if 10 <= value <= 11:
            return "mdi:arrow-top-right"  # SW (South-West)t
        if 12 <= value <= 13:
            return "mdi:arrow-right"  # W (West)
        if 14 <= value <= 15:
            return "mdi:arrow-bottom-right"  # NW (North-West)
        return "mdi:compass-outline"  # Fallback, should not happen

    # ---- Get the timeout time for a station or a sensor ----
    def get_timeout(self, sensor_id: str):
        """Return the timeout time for a station or sensor."""

        try:
            timeout_val = TIMEOUT_MAPPING[sensor_id[:2].upper()]
        except KeyError:
            timeout_val = 0
        return timeout_val

    # ---- Update ----
    async def async_update(self) -> None:
        """Manual Updating."""
        await self.coordinator.async_request_refresh()


# ---- Class to store a history, specially for rain sensor to calculate rain of "last hour", "last 24 hours" ----
class SensorHistory:
    """History queue."""

    def __init__(self, max_age_minutes=60) -> None:
        """Initalaize history queue."""
        self.max_age = max_age_minutes * 60
        self.data: deque[tuple[float, int]] = deque()  # Stores (value, timestamp)

    def add_measurement(self, value, ts):
        """Add new value with time stamp."""
        ts_last = 0
        val_last = 0
        length = len(self.data)
        if length != 0:
            entry_last = self.data[-1]
            ts_last = entry_last[1]
            val_last = entry_last[0]
        if (ts_last != ts) & (val_last != value):
            self.data.append((value, ts))
            self.cleanup()

    def cleanup(self):
        """Remove entries older max_age seconds."""
        utc_now = datetime.now()
        utc_now_ts = int(utc_now.timestamp())
        run = 1
        while self.data and (run == 1):
            ts1 = int(self.data[0][1])
            ts2 = utc_now_ts - self.max_age
            if ts1 < ts2:
                self.data.popleft()
            else:
                run = 0

    def get_data(self):
        """Return list with values."""
        return list(self.data)

    def get_oldest_and_newest(self):
        """Return oldest and newest measuerement tuple."""
        if not self.data:
            return None, None  # If list is empty
        return self.data[0], self.data[-1]  # First(oldest) and last(newest) entry
