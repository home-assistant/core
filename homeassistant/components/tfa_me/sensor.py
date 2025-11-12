"""TFA.me station integration: sensor.py."""

from datetime import datetime
import logging
from typing import Any

from tfa_me_ha_local.history import SensorHistory

from homeassistant.components.sensor import SensorEntity, SensorStateClass, StateType
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_MAPPING, DOMAIN, ICON_MAPPING, TIMEOUT_MAPPING
from .coordinator import TFAmeConfigEntry, TFAmeDataCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TFAmeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TFA.me as Sensor."""

    # Get coordinator
    coordinator = hass.data.setdefault(DOMAIN, {})[entry.entry_id]
    # Initialize first refresh/request and wait for parsed JSON data from coordinator

    try:
        # Wait for coordinator.async_config_entry_first_refresh() then collect all entities
        sensors_start = []
        for unique_id in coordinator.data:
            sensor_id = coordinator.data[unique_id]["sensor_id"]
            if unique_id not in coordinator.sensor_entity_list:
                if "_txt" not in unique_id:
                    sensors_start.append(
                        TFAmeSensorEntity(coordinator, sensor_id, unique_id)
                    )
                    coordinator.sensor_entity_list.append(unique_id)

        # Add all entities
        async_add_entities(sensors_start, True)
        coordinator.entities_added = 1

    except Exception as error:
        raise ConfigEntryNotReady(
            f"Station not available: {error}"
        ) from error  # Catch errors here

    async def async_discover_new_entities():
        """Find new sensors in coordinator data and register them."""
        coordinator = entry.coordinator

        new_sensors = []
        for entity_id in coordinator.data:
            sensor_id = coordinator.data[entity_id]["sensor_id"]
            if entity_id not in coordinator.sensor_entity_list:
                if "_txt" not in entity_id:
                    new_sensors.append(
                        TFAmeSensorEntity(coordinator, sensor_id, entity_id)
                    )
                    coordinator.sensor_entity_list.append(entity_id)

        if new_sensors:
            async_add_entities(new_sensors)

    # Save function in Home Assistant so that it can be called as service
    hass.data[DOMAIN][
        entry.entry_id
    ].async_discover_new_entities = async_discover_new_entities


class TFAmeSensorEntity(CoordinatorEntity, SensorEntity):
    """TFA.me sensor entity, represents in HA a single measurement value of a sensor."""

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
            self._initialized_once = False
            self.coordinator = coordinator
            self._attr_unique_id = entity_id  # This is the unique ID (sets unique_id), will never be changed
            self.host = coordinator.host
            self.name_with_station_id = coordinator.name_with_station_id
            self.entity_id = entity_id  # User can edit this entity ID
            self.uid: str = entity_id
            self.gateway_id = self.coordinator.data[self.uid]["gateway_id"]

            self.sensor_id = sensor_id
            label = (
                f"via {self.gateway_id}" if getattr(self, "gateway_id", None) else "via"
            )
            self._attr_labels: list[str] = [label]

            self._attr_icon = ""
            self._attr_name = entity_id  # just the entity ID
            ids_str = f"{sensor_id}_{self.gateway_id}"
            self._attr_device_info = {
                "identifiers": {
                    (
                        DOMAIN,
                        ids_str,
                    )  # Entities for sensors
                },  # Unique ID for device/sensor
                "name": self.format_string_tfa_id(
                    self.sensor_id, self.gateway_id, self.name_with_station_id
                ),  # 'TFA.me XXX-XXX-XXX'
                "manufacturer": "TFA/Dostmann",
                "model": self.format_string_tfa_type(
                    sensor_id
                ),  # 'Sensor/Station type XX'
            }

            # Some rain specials
            if self.uid.endswith("_rain"):
                self._attr_state_class = SensorStateClass.TOTAL_INCREASING
            if "_rain_hour" in self.uid:
                self.rain_history: SensorHistory = SensorHistory(max_age_minutes=60)
            if "_rain_24hours" in self.uid:
                self.rain_history_24: SensorHistory = SensorHistory(
                    max_age_minutes=(24 * 60)
                )
                self._attr_state_class = SensorStateClass.TOTAL

            # If this is a station add URL to station
            hex_value = int(sensor_id[:2], 16)
            if hex_value < 160:
                self._attr_device_info["configuration_url"] = (
                    f"http://{coordinator.host}/ha_menu"
                )

            # Add icon for measurement
            self.init_measure_value = 0
            self.measure_name = self.coordinator.data[self.uid]["measurement"]
            self.init_measure_value = self.coordinator.data[self.uid]["value"]

            self._attr_icon = self.get_icon(
                self.measure_name, float(self.init_measure_value)
            )

        except (ValueError, TypeError, KeyError):
            return

    async def async_added_to_hass(self) -> None:
        """Called once if entity is added to HA instance."""
        await super().async_added_to_hass()
        self._initialized_once = True

        if self.name_with_station_id:
            ent_reg = er.async_get(self.hass)
            reg_entry = ent_reg.async_get(self.entity_id)
            if not reg_entry:
                return

            # Set a label if not available in registry
            if not reg_entry.labels:
                # User labels are not overwritten
                if self.entity_id:
                    ent_reg.async_update_entity(
                        self.entity_id, labels=set(self._attr_labels)
                    )

    def _handle_coordinator_update(self) -> None:
        """Called when coordinator has new data, used to update rain histories."""

        if "rain_hour" in self.uid:
            try:
                value = self.coordinator.data[self.uid]["value"]
                ts = self.coordinator.data[self.uid]["ts"]
                self.rain_history.add_measurement(value, ts)
                self.rain_history.cleanup()

            except (ValueError, TypeError, KeyError):
                value = 0

        if "rain_24hours" in self.uid:
            try:
                value = self.coordinator.data[self.uid]["value"]
                ts = self.coordinator.data[self.uid]["ts"]
                self.rain_history_24.add_measurement(value, ts)
                self.rain_history_24.cleanup()

            except (ValueError, TypeError, KeyError):
                value = 0

        # Update state in HA
        super()._handle_coordinator_update()

    def format_string_tfa_id(self, s: str, gw_id: str, name_with_station_id: bool):
        """String helper for sensor names, convert string 'xxxxxxxxx' into 'TFA.me XXX-XXX-XXX'."""
        if name_with_station_id:
            return f"TFA.me {s[:3].upper()}-{s[3:6].upper()}-{s[6:].upper()} ({gw_id.upper()})"

        return f"TFA.me {s[:3].upper()}-{s[3:6].upper()}-{s[6:].upper()}"

    def format_string_tfa_type(self, s: str):
        """String helper for sensor/station types, convert string 'xxxxxxxxx' into 'Sensor/station type XX'."""

        type_id: str = (s[:2]).upper()
        info_str: str = "?"
        try:
            info_str = DEVICE_MAPPING[type_id]
        except KeyError:
            info_str = "?"
        return info_str

    @property
    def name(self) -> str:
        """Name of sensors in Home Assistant, "ID MEASUEREMENT",  e.g. "A01234456 Temperature."""
        try:
            sensor_data = self.coordinator.data[self.uid]
            str1 = f"{sensor_data['measurement'].capitalize()}"
            str2 = str1.replace("Rssi", "RSSI")
            str3 = str2.replace("Co2", "CO2")
            return str3.replace("_", " ")
        except (ValueError, TypeError, KeyError):
            return "None"

    @property
    def measurement_name(self):
        """Name of measurement, e.g. 'temperature'."""
        try:
            measurement_name = self.coordinator.data[self.uid]["measurement"]
        except (ValueError, TypeError, KeyError):
            return None

        return measurement_name

    @property
    def native_value(self) -> StateType:
        """Actual measurement value of an entity itself."""
        try:
            # Is measurement value still valid or old ?
            last_update_ts: int = int(self.coordinator.data[self.uid]["ts"])
            utc_now = datetime.now()
            utc_now_ts = int(utc_now.timestamp())
            timeout = self.get_timeout(self.sensor_id)
            if (utc_now_ts - last_update_ts) <= (timeout):
                measurement_value = self.coordinator.data[self.uid]["value"]

                # Is this rain sensor relative value since last restart
                if "rain_rel" in self.uid:
                    measurement_value = float(
                        float(measurement_value) - float(self.init_measure_value)
                    )
                    measurement_value = round(measurement_value, 1)

                # Is this rain sensor last hour ?
                if "rain_hour" in self.uid:
                    reset_rain = self.coordinator.data[self.uid]["reset_rain"]
                    if reset_rain:
                        self.rain_history = SensorHistory(max_age_minutes=60)
                        self.coordinator.data[self.uid]["reset_rain"] = False

                    measurement_value = float(0)
                    if len(self.rain_history.data) >= 2:
                        oldest, newest = self.rain_history.get_oldest_and_newest()
                        measurement_value = float(newest[0]) - float(oldest[0])
                        measurement_value = round(measurement_value, 1)

                # Is this rain sensor last 24 hours ?
                if "rain_24hours" in self.uid:
                    reset_rain = self.coordinator.data[self.uid]["reset_rain"]
                    if reset_rain:
                        self.rain_history_24 = SensorHistory(max_age_minutes=(24 * 60))
                        self.coordinator.data[self.uid]["reset_rain"] = False

                    measurement_value = float(0)
                    if len(self.rain_history_24.data) >= 2:
                        oldest, newest = self.rain_history_24.get_oldest_and_newest()
                        measurement_value = float(newest[0]) - float(oldest[0])
                        measurement_value = round(measurement_value, 1)

                # Is this wind sensor degrees entity ?
                if "wind_direction_deg" in self.uid:
                    try:
                        str_wind_deg = self.uid
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
                measurement_value = None  # STATE_UNAVAILABLE

        except (ValueError, TypeError, KeyError):
            return None  # Wrong data, Home Assistant shows sensor as "unavailable"

        return measurement_value

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Unit of measurement value,  e.g. for wind speed unit is "m/s"."""

        try:
            unit = self.coordinator.data[self.uid]["unit"]
            if unit is None:
                return None  # HA shows "unavailable"
            return str(unit)
        except (ValueError, TypeError, KeyError):
            return ""

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Extra attributes dictionary for an entity: sensor_name, measurement, timestamp, icon."""

        try:
            sensor_data = self.coordinator.data[self.uid]
            return {
                "sensor_name": sensor_data["sensor_name"],
                "measurement": sensor_data["measurement"],
                "timestamp": sensor_data["timestamp"],
                "icon": self._attr_icon,
                "Via TFA.me station": self.gateway_id.upper(),
            }
        except (ValueError, TypeError, KeyError):
            return {}

    @property
    def icon(self) -> str:
        """Returns icon based on actual measurement value."""
        value = self.native_value
        return self.get_icon(self.measurement_name, value)

    def get_icon(self, measurement_type, value_state):
        """Return an icon for measurement type based on measurement value (see also MDI list)."""

        if value_state is None:
            value = value_state
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

        # Battery: 1 = low battery, 0 = good battery
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
        # value >= 4:
        return ICON_MAPPING["rain"]["heavy"]

    def get_wind_direction_icon(self, value):
        """Return icon for wind direction based on value 0 to 15."""

        # Remark: there are only 8 MDI arrows for direction but 16 wind direction so icon does not match optimal.
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
            return "mdi:arrow-top-right"  # SW (South-West)
        if 12 <= value <= 13:
            return "mdi:arrow-right"  # W (West)
        if 14 <= value <= 15:
            return "mdi:arrow-bottom-right"  # NW (North-West)
        return "mdi:compass-outline"  # Fallback, should not happen

    def get_timeout(self, sensor_id: str):
        """Return the timeout time for a station or sensor."""

        try:
            timeout_val = TIMEOUT_MAPPING[sensor_id[:2].upper()]
        except KeyError:
            timeout_val = 0
        return timeout_val

    async def async_update(self) -> None:
        """Manual Updating."""
        await self.coordinator.async_request_refresh()
