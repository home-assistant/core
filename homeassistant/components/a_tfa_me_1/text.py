"""TFA.me station integration: text.py."""

from datetime import datetime
from typing import Any

from homeassistant.components.text import TextEntity

from .const import DEVICE_MAPPING, DOMAIN, ICON_MAPPING, TIMEOUT_MAPPING
from .coordinator import TFAmeDataCoordinator


# ---- TFA.me text entity ----
class TFAmeTextEntity(TextEntity):
    """Represents in Home Assistant a text for a sensor."""

    _attr_has_entity_name = True
    _attr_should_poll = True

    def __init__(
        self,
        coordinator: TFAmeDataCoordinator,
        sensor_id: str,
        entity_id: str,
    ) -> None:
        """Initialize text entity."""
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
                )  # this IDs are used to ground entities
            },  # Unique ID for device/sensor
            "name": self.format_string_tfa_id(
                self.sensor_id, self.gateway_id, self.multiple_entities
            ),  # 'TFA.me XXX-XXX-XXX'
            "manufacturer": "TFA/Dostmann",
            "model": self.format_string_tfa_type(sensor_id),  # 'Sensor/Station type XX'
            # "sw_version": "1.0",
            # "hw_version": "1.0",
            # "serial_number": "123"
        }

        # Add icon for measurement
        try:
            self.measure_name = self.coordinator.data[self.entity_id]["measurement"]
        except (ValueError, TypeError, KeyError):
            self.measure_name = (
                ""  # Wrong data, Home Assistant shows sensor as "unavailable"
            )

        self.init_measure_value = self.coordinator.data[self.entity_id]["value"]

        if self.init_measure_value is not None:
            self._attr_icon = self.get_icon(
                self.measure_name, float(self.init_measure_value)
            )
        else:
            self._attr_icon = ""

    # ---- Property: text value of an entity itself ----
    @property
    def native_value(
        self,
    ) -> str | None:  # -> StateType:  # None | int | float | str | StateType:
        """Actual measurement value."""
        try:
            # Is measurement value still valid or old
            last_update_ts: int = int(self.coordinator.data[self.entity_id]["ts"])
            utc_now = datetime.now()
            utc_now_ts = int(utc_now.timestamp())
            timeout = self.get_timeout(self.sensor_id)
            if (utc_now_ts - last_update_ts) <= (timeout):
                text_str = self.coordinator.data[self.entity_id]["text"]
            else:
                text_str = None

        except (ValueError, TypeError, KeyError):
            return None  # Wrong data, Home Assistant shows sensor as "unavailable"

        return text_str

    # ---- String helper for sensor names ----
    def format_string_tfa_id(self, s: str, gw_id: str, multiple_entities: bool):
        """Convert string 'xxxxxxxxx' into 'TFA.me XXX-XXX-XXX'."""
        if multiple_entities:
            return f"TFA.me {s[:3].upper()}-{s[3:6].upper()}-{s[6:].upper()}({gw_id.upper()})"
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

    # ---- Property: Name of sensor entity in HA: "ID MEASUEREMENT",  e.g. "A01234456 Wind direction text" ----
    @property
    def name(self) -> str:
        """Name of sensors in Home Assistant."""
        try:
            sensor_data = self.coordinator.data[self.entity_id]
            str1 = f"{sensor_data['sensor_name']} {sensor_data['measurement'].capitalize()}"
            return str1.replace("_", " ")
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

    # ---- Property: Extra attributes dictionary for an entity ----
    # "sensor_name": Sensor ID, e.g. "A21234456"
    # "measurement": Name of measurement value, e.g. "wind direction text"
    # "timestamp"  : UTC timestamp, e.g. "2025-03-06T08:46:01Z"
    # "icon"       : Icon for a measurement value, e.g. "mdi:arrow-up"
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
        value = self.coordinator.data[self.entity_id]["value"]
        # get the icon
        return self.get_icon(self.measurement_name, value)

    # ---- Get an icon for measurement type based on measurement value (see MDI list) ----
    def get_icon(self, measurement_type, value_state):
        """Return icon for a sensor type."""

        if value_state is None:
            value = value_state
        else:
            try:
                value = float(value_state)
            except (ValueError, TypeError, KeyError):
                value = 0

        # Wind direction text
        if measurement_type == "wind_direction_text":
            return self.get_wind_direction_icon(value)

        # Lowbatt as text
        if measurement_type == "lowbatt_text":
            # Battery: 0 = low battery, 1 = good battery
            return (
                ICON_MAPPING["lowbatt"]["low"]
                if value == 1
                else ICON_MAPPING["lowbatt"]["full"]
            )

        # Unknown measurement type
        return "mdi:help-circle"  # Fallback-Icon

    # ---- Get an icon for wind direction based on values (o...15) ----
    # Remark: there are only 8 arrows for direction but 16 wind direction so icon does not match optimal
    def get_wind_direction_icon(self, value):
        """Return icon for wind direction based on value 0 to 15."""
        if value is None:
            return "mdi:compass-outline"

        if 0 <= value <= 1:
            return "mdi:arrow-down"  # N (North)
        if 2 <= value <= 3:
            return "mdi:aarrow-bottom-left"  # NE (North-East)
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

    # ----  ----
    async def async_update(self) -> None:
        """Manual Updating."""
        await self.coordinator.async_request_refresh()
