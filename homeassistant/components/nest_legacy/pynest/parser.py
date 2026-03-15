"""Data parsing for the Nest API."""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import logging
import time
from typing import Any

from .enums import (
    HotWaterMode,
    LockBoltActor,
    LockBoltState,
    StructureMode,
    TemperatureScale,
    ThermostatHvacMode,
    ThermostatHvacState,
)
from .models import (
    NestBatteryProtect,
    NestCamera,
    NestDevice,
    NestDoorbell,
    NestHeatLink,
    NestLock,
    NestProtect,
    NestStructure,
    NestTempSensor,
    NestThermostat,
    NestWiredProtect,
)
from .protobuf_gen.nest.trait import (
    audio_pb2 as nest_audio_pb2,
    hvac_pb2 as nest_hvac_pb2,
    located_pb2 as nest_located_pb2,
    occupancy_pb2 as nest_occupancy_pb2,
    safety_pb2 as nest_safety_pb2,
    sensor_pb2 as nest_sensor_pb2,
    structure_pb2 as nest_structure_pb2,
    ui_pb2 as nest_ui_pb2,
)
from .protobuf_gen.nest.trait.product import (
    camera_pb2 as nest_camera_pb2,
    doorbell_pb2 as nest_doorbell_pb2,
    protect_pb2 as nest_protect_pb2,
)
from .protobuf_gen.weave.trait import (
    description_pb2 as weave_description_pb2,
    heartbeat_pb2 as weave_heartbeat_pb2,
    power_pb2 as weave_power_pb2,
    security_pb2 as weave_security_pb2,
)


def _round_temp(temp: Any, scale: TemperatureScale | None) -> float | None:
    """Round temperature to nearest 0.5 C or 1 F based on the device's scale."""
    if temp is None:
        return None
    try:
        temp_float = float(temp)
    except ValueError, TypeError:
        return None
    if scale == TemperatureScale.FAHRENHEIT:
        temp_f = round(temp_float * 1.8 + 32.0)
        return (temp_f - 32.0) / 1.8
    return round(temp_float * 2.0) / 2.0


def _scale_value(
    value: float,
    source_min: float,
    source_max: float,
    target_min: float,
    target_max: float,
) -> float:
    """Scale a value from a source range to a target range."""
    if source_max == source_min:
        return float(target_min)
    value = max(source_min, min(source_max, value))
    return ((value - source_min) * (target_max - target_min)) / (
        source_max - source_min
    ) + target_min


def _get_protobuf_location(traits: dict[str, Any]) -> str | None:
    """Extract location from protobuf traits."""
    loc_trait: nest_located_pb2.DeviceLocatedSettingsTrait | None = traits.get(
        nest_located_pb2.DeviceLocatedSettingsTrait.DESCRIPTOR.full_name
    )
    if not loc_trait:
        return None
    if loc_trait.HasField("whereLabel"):
        return loc_trait.whereLabel.literal
    if loc_trait.HasField("fixtureNameLabel"):
        return loc_trait.fixtureNameLabel.literal
    return None


def _milli_volt_to_percentage(state: int) -> float:
    """Convert battery level in mV to a percentage.

    The battery life percentage in devices is estimated using slopes from the L91 battery's datasheet.
    This is a rough estimation, and the battery life percentage is not linear.

    Tests on various devices have shown accurate results.
    """
    if 3000 < state <= 6000:
        if 4950 < state <= 6000:
            slope = 0.001816609
            yint = -8.548096886
        elif 4800 < state <= 4950:
            slope = 0.000291667
            yint = -0.991176471
        elif 4500 < state <= 4800:
            slope = 0.001077342
            yint = -4.730392157
        else:
            slope = 0.000434641
            yint = -1.825490196

        return max(0, min(100, round(((slope * state) + yint) * 100)))

    return 0.0


def _get_model_from_serial(serial_number: str | None) -> str:
    """Determine thermostat model from serial number as a fallback."""
    if not serial_number:
        return "Thermostat"
    prefix = serial_number[:2]
    if prefix == "15":
        return "Thermostat E"
    if prefix in ("09", "10"):
        return "Learning Thermostat (3rd gen)"
    if prefix == "02":
        return "Learning Thermostat (2nd gen)"
    if prefix == "01":
        return "Learning Thermostat (1st gen)"
    return "Thermostat"


@dataclass
class ParsedData:
    """Container for all parsed data."""

    devices: list[NestDevice]


_LOGGER = logging.getLogger(__name__)


class NestParser:
    """Parses raw Nest API data into structured objects."""

    def parse_all(self, raw_data: dict[str, Any]) -> ParsedData:
        """Process all raw data into a device list."""
        devices: list[NestDevice] = []
        thermostats: list[NestThermostat] = []

        wheres_map = self._build_wheres_map(raw_data)

        for key, value in raw_data.items():
            try:
                device: NestDevice | None = None
                if key.startswith("topaz."):
                    device = self._parse_protect(key, value, raw_data, wheres_map)
                elif key.startswith("device."):
                    if device := self._parse_thermostat(
                        key, value, raw_data, wheres_map
                    ):
                        thermostats.append(device)
                elif key.startswith("kryptonite."):
                    device = self._parse_tempsensor(key, value, raw_data, wheres_map)
                elif key.startswith("quartz."):
                    device = self._parse_camera(key, value, wheres_map)
                elif key.startswith("structure."):
                    device = self._parse_structure(key, value, raw_data)
                elif key.startswith("DEVICE_"):
                    # Handle protobuf devices
                    if weave_security_pb2.BoltLockTrait.DESCRIPTOR.full_name in value:
                        device = self._parse_protobuf_lock(key, value)
                    elif nest_hvac_pb2.HvacControlTrait.DESCRIPTOR.full_name in value:
                        if device := self._parse_protobuf_thermostat(
                            key, value, raw_data
                        ):
                            thermostats.append(device)
                    elif (
                        nest_sensor_pb2.SmokeTrait.DESCRIPTOR.full_name in value
                        or nest_sensor_pb2.CarbonMonoxideTrait.DESCRIPTOR.full_name
                        in value
                        or nest_safety_pb2.SafetyAlarmSmokeTrait.DESCRIPTOR.full_name
                        in value
                    ):
                        device = self._parse_protobuf_protect(key, value, raw_data)
                    elif (
                        nest_camera_pb2.StreamingProtocolTrait.DESCRIPTOR.full_name
                        in value
                    ):
                        device = self._parse_protobuf_camera(key, value)
                    elif (
                        nest_sensor_pb2.TemperatureTrait.DESCRIPTOR.full_name in value
                        and nest_hvac_pb2.HvacControlTrait.DESCRIPTOR.full_name
                        not in value
                        and nest_sensor_pb2.HumidityTrait.DESCRIPTOR.full_name
                        not in value
                    ):
                        device = self._parse_protobuf_sensor(key, value, raw_data)
                    elif (
                        nest_structure_pb2.StructureInfoTrait.DESCRIPTOR.full_name
                        in value
                    ):
                        device = self._parse_protobuf_structure(key, value)

                if device:
                    devices.append(device)
            except (KeyError, TypeError, ValueError) as e:
                _LOGGER.warning("Skipping device %s due to a parsing error: %s", key, e)

        # Second pass to create derived devices like Heat Link
        devices.extend(
            heatlink
            for thermostat in thermostats
            if (heatlink := self._create_heatlink(thermostat))
        )

        return ParsedData(devices=devices)

    def _build_wheres_map(self, raw_data: dict[str, Any]) -> dict[str, str]:
        """Build a map of where_id to location name."""
        wheres_map: dict[str, str] = {}
        for key, value in raw_data.items():
            if key.startswith("where."):
                for where in value.get("wheres", []):
                    if "where_id" in where and "name" in where:
                        wheres_map[where["where_id"]] = where["name"]
        return wheres_map

    def _get_location(
        self, data: dict[str, Any], wheres_map: dict[str, str]
    ) -> str | None:
        """Get the location name for a device."""
        where_id = data.get("where_id")
        if where_id is None:
            return None
        return wheres_map.get(where_id)

    def _parse_protect(
        self,
        key: str,
        value: dict[str, Any],
        raw_data: dict[str, Any],
        wheres_map: dict[str, str],
    ) -> NestProtect | None:
        """Parse a Nest Protect device."""
        device_id = key.split(".")[1]
        widget_key = f"widget_track.{device_id}"
        online = raw_data.get(widget_key, {}).get("online", False)
        replace_by_ts = value.get("replace_by_date_utc_secs")
        replace_by_date = (
            datetime.datetime.fromtimestamp(replace_by_ts, datetime.UTC).date()
            if replace_by_ts
            else None
        )
        batt_mv = value.get("battery_level", 0)
        battery_voltage = batt_mv / 1000.0 if batt_mv else None

        if value.get("wired_or_battery") == 0:
            return NestWiredProtect(
                object_key=key,
                serial_number=value["serial_number"],
                location=self._get_location(value, wheres_map),
                name=value.get("description", "Protect"),
                model=value.get("model"),
                software_version=value.get("software_version"),
                mac_address=value.get("wifi_mac_address"),
                online=online,
                smoke_status=value.get("smoke_status", 0) != 0,
                co_status=value.get("co_status", 0) != 0,
                heat_status=value.get("heat_status", 0) != 0,
                battery_level=_milli_volt_to_percentage(batt_mv),
                battery_voltage=battery_voltage,
                battery_health_state=value.get("battery_health_state", 0),
                replace_by_date=replace_by_date,
                occupancy=not value.get("auto_away", True),
                line_power_present=value.get("line_power_present", False),
                night_light_enable=value.get("night_light_enable", False),
                steam_detection_enable=value.get("steam_detection_enable", False),
                night_light_brightness=value.get("night_light_brightness"),
                component_speaker_test_passed=value.get(
                    "component_speaker_test_passed", True
                ),
                component_smoke_test_passed=value.get(
                    "component_smoke_test_passed", True
                ),
                component_co_test_passed=value.get("component_co_test_passed", True),
                component_wifi_test_passed=value.get(
                    "component_wifi_test_passed", True
                ),
                component_led_test_passed=value.get("component_led_test_passed", True),
                component_pir_test_passed=value.get("component_pir_test_passed", True),
                component_buzzer_test_passed=value.get(
                    "component_buzzer_test_passed", True
                ),
                component_hum_test_passed=value.get("component_hum_test_passed", True),
                removed_from_base=value.get("removed_from_base", False),
                latest_manual_test_end_utc_secs=value.get(
                    "latest_manual_test_end_utc_secs", 0
                ),
                last_audio_self_test_end_utc_secs=value.get(
                    "last_audio_self_test_end_utc_secs", 0
                ),
                ntp_green_led_enable=value.get("ntp_green_led_enable", False),
                heads_up_enable=value.get("heads_up_enable", False),
            )
        return NestBatteryProtect(
            object_key=key,
            serial_number=value["serial_number"],
            location=self._get_location(value, wheres_map),
            name=value.get("description", "Protect"),
            model=value.get("model"),
            software_version=value.get("software_version"),
            mac_address=value.get("wifi_mac_address"),
            online=online,
            smoke_status=value.get("smoke_status", 0) != 0,
            co_status=value.get("co_status", 0) != 0,
            heat_status=value.get("heat_status", 0) != 0,
            battery_level=_milli_volt_to_percentage(batt_mv),
            battery_voltage=battery_voltage,
            battery_health_state=value.get("battery_health_state", 0),
            replace_by_date=replace_by_date,
            night_light_enable=value.get("night_light_enable", False),
            steam_detection_enable=value.get("steam_detection_enable", False),
            night_light_brightness=value.get("night_light_brightness"),
            component_speaker_test_passed=value.get(
                "component_speaker_test_passed", True
            ),
            component_smoke_test_passed=value.get("component_smoke_test_passed", True),
            component_co_test_passed=value.get("component_co_test_passed", True),
            component_wifi_test_passed=value.get("component_wifi_test_passed", True),
            component_led_test_passed=value.get("component_led_test_passed", True),
            component_pir_test_passed=value.get("component_pir_test_passed", True),
            component_buzzer_test_passed=value.get(
                "component_buzzer_test_passed", True
            ),
            component_hum_test_passed=value.get("component_hum_test_passed", True),
            removed_from_base=value.get("removed_from_base", False),
            latest_manual_test_end_utc_secs=value.get(
                "latest_manual_test_end_utc_secs", 0
            ),
            last_audio_self_test_end_utc_secs=value.get(
                "last_audio_self_test_end_utc_secs", 0
            ),
            ntp_green_led_enable=value.get("ntp_green_led_enable", False),
            heads_up_enable=value.get("heads_up_enable", False),
        )

    def _parse_thermostat(
        self,
        key: str,
        value: dict[str, Any],
        raw_data: dict[str, Any],
        wheres_map: dict[str, str],
    ) -> NestThermostat | None:
        """Parse a Nest Thermostat device."""
        device_id = key.split(".")[1]
        shared_key = f"shared.{device_id}"
        if shared_key not in raw_data:
            return None
        shared_data = raw_data[shared_key]

        data: dict[str, Any] = {**value, **shared_data}
        track_key = f"track.{device_id}"
        online = raw_data.get(track_key, {}).get("online", False)

        # Occupancy
        link_key = f"link.{device_id}"
        structure_key = raw_data.get(link_key, {}).get("structure")
        occupancy = (
            not raw_data.get(structure_key, {}).get("away", True)
            if structure_key
            else False
        )

        hvac_state = ThermostatHvacState.OFF
        if (
            data.get("hvac_heater_state")
            or data.get("hvac_heat_x2_state")
            or data.get("hvac_heat_x3_state")
            or data.get("hvac_aux_heater_state")
            or data.get("hvac_alt_heat_state")
            or data.get("hvac_alt_heat_x2_state")
            or data.get("hvac_emer_heat_state")
        ):
            hvac_state = ThermostatHvacState.HEATING
        elif (
            data.get("hvac_ac_state")
            or data.get("hvac_cool_x2_state")
            or data.get("hvac_cool_x3_state")
        ):
            hvac_state = ThermostatHvacState.COOLING
        elif data.get("fan_timer_timeout", 0) > 0 or data.get("hvac_fan_state", False):
            hvac_state = ThermostatHvacState.FAN

        temp_scale_value = data.get("temperature_scale")
        try:
            temp_scale = (
                TemperatureScale(temp_scale_value)
                if temp_scale_value
                else TemperatureScale.CELSIUS
            )
        except ValueError, TypeError:
            _LOGGER.warning(
                "Unsupported value for TemperatureScale: '%s'. Defaulting to Celsius",
                temp_scale_value,
            )
            temp_scale = TemperatureScale.CELSIUS

        is_eco = data.get("eco", {}).get("mode") in ("auto-eco", "manual-eco")
        if is_eco:
            target_low = data.get("away_temperature_low")
            target_high = data.get("away_temperature_high")

            heat_enabled = data.get("away_temperature_low_enabled", False)
            cool_enabled = data.get("away_temperature_high_enabled", False)

            if heat_enabled and not cool_enabled:
                hvac_mode = ThermostatHvacMode.HEAT
            elif not heat_enabled and cool_enabled:
                hvac_mode = ThermostatHvacMode.COOL
            elif heat_enabled and cool_enabled:
                hvac_mode = ThermostatHvacMode.RANGE
            else:
                hvac_mode = ThermostatHvacMode.OFF
        else:
            target_low = data.get("target_temperature_low")
            target_high = data.get("target_temperature_high")

            target_temp_type = data.get("target_temperature_type", "off")
            if target_temp_type == "eco":
                hvac_mode = ThermostatHvacMode.RANGE
            else:
                try:
                    hvac_mode = ThermostatHvacMode(target_temp_type)
                except ValueError:
                    _LOGGER.warning(
                        "Unsupported value for ThermostatHvacMode: '%s'. Defaulting to OFF",
                        target_temp_type,
                    )
                    hvac_mode = ThermostatHvacMode.OFF

        current_temperature = data.get("current_temperature")

        # Check for active remote temperature sensor
        rcs_settings_key = f"rcs_settings.{device_id}"
        if rcs_settings_key in raw_data:
            rcs_data = raw_data[rcs_settings_key]
            active_sensors = rcs_data.get("active_rcs_sensors", [])
            if active_sensors:
                sensor_key = active_sensors[0]
                if sensor_key in raw_data:
                    sensor_data = raw_data[sensor_key]
                    current_temperature = sensor_data.get("current_temperature")

        current_temperature = _round_temp(current_temperature, temp_scale)
        target_temperature = _round_temp(data.get("target_temperature"), temp_scale)
        target_low = _round_temp(target_low, temp_scale)
        target_high = _round_temp(target_high, temp_scale)

        fan_timer_speed_str = data.get("fan_timer_speed", "stage0").replace("stage", "")
        try:
            fan_timer_speed = (
                int(fan_timer_speed_str)
                if fan_timer_speed_str and fan_timer_speed_str != "none"
                else 1
            )
        except ValueError:
            fan_timer_speed = 1

        fan_max_speed_str = data.get("fan_capabilities", "stage1").replace("stage", "")
        try:
            fan_max_speed = (
                int(fan_max_speed_str)
                if fan_max_speed_str and fan_max_speed_str != "none"
                else 1
            )
        except ValueError:
            fan_max_speed = 1

        batt_volts = data.get("battery_level")

        return NestThermostat(
            object_key=key,
            serial_number=value["serial_number"],
            location=self._get_location(value, wheres_map),
            name=value.get("description", "Thermostat"),
            model=value.get("model") or _get_model_from_serial(value["serial_number"]),
            software_version=value.get("software_version"),
            mac_address=value.get("mac_address"),
            online=online,
            temperature_scale=temp_scale,
            current_temperature=current_temperature,
            backplate_temperature=_round_temp(
                value.get("backplate_temperature"), temp_scale
            ),
            target_temperature=target_temperature,
            target_temperature_low=target_low,
            target_temperature_high=target_high,
            current_humidity=data.get("current_humidity"),
            target_humidity=data.get("target_humidity"),
            hvac_state=hvac_state,
            hvac_mode=hvac_mode,
            is_eco_mode=is_eco,
            leaf=data.get("leaf", False),
            temperature_lock=data.get("temperature_lock", False),
            can_heat=data.get("can_heat", False),
            can_cool=data.get("can_cool", False),
            has_fan=data.get("has_fan", False),
            fan_state=data.get("fan_timer_timeout", 0) > time.time(),
            fan_timer_speed=fan_timer_speed,
            fan_max_speed=fan_max_speed,
            fan_duration=data.get("fan_duration", 900),
            fan_timer_timeout=data.get("fan_timer_timeout", 0),
            has_dehumidifier=data.get("has_dehumidifier", False),
            dehumidifier_state=data.get("dehumidifier_state", False),
            has_humidifier=data.get("has_humidifier", False),
            humidifier_state=data.get("humidifier_state", False),
            occupancy=occupancy,
            battery_level=_scale_value(batt_volts, 3.6, 3.9, 0, 100)
            if batt_volts is not None
            else 0.0,
            battery_voltage=batt_volts,
            has_hot_water_control=data.get("has_hot_water_control", False),
            has_hot_water_temperature=data.get("has_hot_water_temperature", False),
            heat_link_model=data.get("heat_link_model"),
            heat_link_serial_number=data.get("heat_link_serial_number"),
            heat_link_sw_version=data.get("heat_link_sw_version"),
            hot_water_active=data.get("hot_water_active", False),
            hot_water_mode=HotWaterMode(data.get("hot_water_mode", "off")),
            hot_water_away_enabled=data.get("hot_water_away_enabled", False),
            hot_water_boost_time_to_end=data.get("hot_water_boost_time_to_end", 0),
            hot_water_temperature=_round_temp(
                data.get("hot_water_temperature"), temp_scale
            ),
            current_water_temperature=_round_temp(
                data.get("current_water_temperature"), temp_scale
            ),
        )

    def _parse_tempsensor(
        self,
        key: str,
        value: dict[str, Any],
        raw_data: dict[str, Any],
        wheres_map: dict[str, str],
    ) -> NestTempSensor | None:
        """Parse a Nest Temperature Sensor."""
        # Legacy API: Check rcs_settings to find association and active status
        associated_thermostat = None
        is_active = False

        # Iterate all rcs_settings buckets to find which one contains this sensor
        for rcs_key, rcs_data in raw_data.items():
            if not rcs_key.startswith("rcs_settings."):
                continue

            rcs_val = rcs_data.get("value", {}) if "value" in rcs_data else rcs_data

            associated_sensors = rcs_val.get("associated_rcs_sensors", [])
            if key in associated_sensors:
                # Found the thermostat this sensor belongs to
                device_id = rcs_key.split(".")[1]
                associated_thermostat = f"device.{device_id}"

                # Check if active
                active_sensors = rcs_val.get("active_rcs_sensors", [])
                if key in active_sensors:
                    is_active = True
                break

        temp_scale = TemperatureScale.CELSIUS
        if associated_thermostat and associated_thermostat in raw_data:
            val = (
                raw_data[associated_thermostat]
                .get("value", {})
                .get("temperature_scale")
                if "value" in raw_data[associated_thermostat]
                else raw_data[associated_thermostat].get("temperature_scale")
            )
            if val == "F":
                temp_scale = TemperatureScale.FAHRENHEIT

        return NestTempSensor(
            object_key=key,
            serial_number=value.get("serial_number", key.split(".")[1]),
            location=self._get_location(value, wheres_map),
            name=value.get("description", "Temperature Sensor"),
            model=value.get("model"),
            software_version=value.get("software_version"),
            online=(time.time() - value.get("last_updated_at", 0)) < 3600 * 4,
            current_temperature=_round_temp(
                value.get("current_temperature"), temp_scale
            ),
            battery_level=value.get("battery_level", 0.0),
            battery_voltage=None,  # REST API reports percentage, not voltage
            associated_thermostat_object_key=associated_thermostat,
            is_active_sensor=is_active,
        )

    def _parse_bool(self, val: Any) -> bool:
        """Parse literal string booleans from older APIs safely."""
        if isinstance(val, str):
            return val.lower() == "true"
        return bool(val)

    def _parse_camera(
        self, key: str, value: dict[str, Any], wheres_map: dict[str, str]
    ) -> NestCamera | None:
        """Parse a Nest Camera or Doorbell."""
        streaming_state = value.get("streaming_state", "")
        model = value.get("model", "")
        props = value.get("properties", {})

        battery_level = None
        battery_voltage = None
        if "rq_battery_battery_volt" in props:
            try:
                battery_voltage = float(props["rq_battery_battery_volt"])
                battery_level = _scale_value(battery_voltage, 0.0, 5.4, 0.0, 100.0)
            except ValueError, TypeError:
                pass

        if "doorbell" in model.lower():
            return NestDoorbell(
                object_key=key,
                serial_number=value["serial_number"],
                location=self._get_location(value, wheres_map),
                name=value.get("description", "Camera"),
                model=model,
                software_version=value.get("software_version"),
                mac_address=value.get("mac_address"),
                online="offline" not in streaming_state,
                streaming_enabled="enabled" in streaming_state,
                audio_enabled=value.get("audio_input_enabled", False),
                is_streaming="streaming" in streaming_state,
                indoor_chime_enabled=props.get("doorbell.indoor_chime.enabled", False),
                has_indoor_chime="indoor_chime" in value.get("capabilities", []),
                doorbell_chime_assist_enabled=props.get(
                    "doorbell.chime_assist.enabled", False
                ),
                irled_enabled=props.get("irled.state") != "always_off",
                status_led_enabled=props.get("statusled.brightness", 1) != 1,
                video_flipped=self._parse_bool(props.get("video.flipped", False)),
                web_url=value.get("web_url"),
                nexus_api_http_server_url=value.get("nexus_api_http_server_url"),
                structure_id=value.get("structure_id"),
                battery_level=battery_level,
                battery_voltage=battery_voltage,
            )
        return NestCamera(
            object_key=key,
            serial_number=value["serial_number"],
            location=self._get_location(value, wheres_map),
            name=value.get("description", "Camera"),
            model=model,
            software_version=value.get("software_version"),
            mac_address=value.get("mac_address"),
            online="offline" not in streaming_state,
            streaming_enabled="enabled" in streaming_state,
            audio_enabled=value.get("audio_input_enabled", False),
            is_streaming="streaming" in streaming_state,
            irled_enabled=props.get("irled.state") != "always_off",
            status_led_enabled=props.get("statusled.brightness", 1) != 1,
            video_flipped=props.get("video.flipped", False),
            web_url=value.get("web_url"),
            nexus_api_http_server_url=value.get("nexus_api_http_server_url"),
            structure_id=value.get("structure_id"),
            battery_level=battery_level,
            battery_voltage=battery_voltage,
        )

    def _parse_structure(
        self, key: str, value: dict[str, Any], raw_data: dict[str, Any]
    ) -> NestStructure | None:
        """Parse a Nest Structure."""
        structure_key = next(
            (key for key in raw_data if key.startswith("STRUCTURE_")), None
        )
        if not structure_key:
            return None  # Cannot control structure without its protobuf key
        mode = StructureMode.HOME
        # The legacy REST API does not distinguish 'Sleep' from 'Home'
        if value.get("vacation_mode"):
            mode = StructureMode.VACATION
        elif value.get("away"):
            mode = StructureMode.AWAY
        return NestStructure(
            object_key=structure_key,
            serial_number=key.split(".")[1],
            name=value.get("name", "Home"),
            mode=mode,
        )

    def _parse_protobuf_lock(
        self,
        key: str,
        traits: dict[str, Any],
    ) -> NestLock | None:
        """Parse a Nest x Yale Lock from protobuf data."""
        bolt_lock_trait: weave_security_pb2.BoltLockTrait | None = traits.get(
            weave_security_pb2.BoltLockTrait.DESCRIPTOR.full_name
        )
        if not bolt_lock_trait:
            return None

        # Determine bolt state
        actuator_state_map = {
            weave_security_pb2.BoltLockTrait.BoltActuatorState.BOLT_ACTUATOR_STATE_LOCKING: LockBoltState.LOCKING,
            weave_security_pb2.BoltLockTrait.BoltActuatorState.BOLT_ACTUATOR_STATE_UNLOCKING: LockBoltState.UNLOCKING,
            weave_security_pb2.BoltLockTrait.BoltActuatorState.BOLT_ACTUATOR_STATE_JAMMED_UNLOCKING: LockBoltState.JAMMED,
            weave_security_pb2.BoltLockTrait.BoltActuatorState.BOLT_ACTUATOR_STATE_JAMMED_LOCKING: LockBoltState.JAMMED,
            weave_security_pb2.BoltLockTrait.BoltActuatorState.BOLT_ACTUATOR_STATE_JAMMED_OTHER: LockBoltState.JAMMED,
        }
        locked_state_map = {
            weave_security_pb2.BoltLockTrait.BoltLockedState.BOLT_LOCKED_STATE_LOCKED: LockBoltState.LOCKED,
            weave_security_pb2.BoltLockTrait.BoltLockedState.BOLT_LOCKED_STATE_UNLOCKED: LockBoltState.UNLOCKED,
        }

        # Check actuator state first (higher priority), then locked state
        bolt_state = actuator_state_map.get(
            bolt_lock_trait.actuatorState,
            locked_state_map.get(bolt_lock_trait.lockedState, LockBoltState.UNKNOWN),
        )

        # Determine bolt actor
        actor_map = {
            weave_security_pb2.BoltLockTrait.BoltLockActorMethod.BOLT_LOCK_ACTOR_METHOD_PHYSICAL: LockBoltActor.PHYSICAL,
            weave_security_pb2.BoltLockTrait.BoltLockActorMethod.BOLT_LOCK_ACTOR_METHOD_KEYPAD_PIN: LockBoltActor.KEYPAD,
            weave_security_pb2.BoltLockTrait.BoltLockActorMethod.BOLT_LOCK_ACTOR_METHOD_REMOTE_USER_EXPLICIT: LockBoltActor.REMOTE,
            weave_security_pb2.BoltLockTrait.BoltLockActorMethod.BOLT_LOCK_ACTOR_METHOD_REMOTE_USER_IMPLICIT: LockBoltActor.REMOTE,
            weave_security_pb2.BoltLockTrait.BoltLockActorMethod.BOLT_LOCK_ACTOR_METHOD_REMOTE_USER_OTHER: LockBoltActor.REMOTE,
            weave_security_pb2.BoltLockTrait.BoltLockActorMethod.BOLT_LOCK_ACTOR_METHOD_REMOTE_DELEGATE: LockBoltActor.REMOTE,
            weave_security_pb2.BoltLockTrait.BoltLockActorMethod.BOLT_LOCK_ACTOR_METHOD_VOICE_ASSISTANT: LockBoltActor.VOICE,
            weave_security_pb2.BoltLockTrait.BoltLockActorMethod.BOLT_LOCK_ACTOR_METHOD_LOCAL_IMPLICIT: LockBoltActor.IMPLICIT,
            weave_security_pb2.BoltLockTrait.BoltLockActorMethod.BOLT_LOCK_ACTOR_METHOD_LOW_POWER_SHUTDOWN: LockBoltActor.IMPLICIT,
        }
        bolt_actor = actor_map.get(
            bolt_lock_trait.boltLockActor.method, LockBoltActor.UNKNOWN
        )

        # Extract other properties from traits
        identity_trait: weave_description_pb2.DeviceIdentityTrait | None = traits.get(
            weave_description_pb2.DeviceIdentityTrait.DESCRIPTOR.full_name
        )
        serial_number = identity_trait.serialNumber if identity_trait else key
        software_version = identity_trait.softwareVersion if identity_trait else None

        label_trait: weave_description_pb2.LabelSettingsTrait | None = traits.get(
            weave_description_pb2.LabelSettingsTrait.DESCRIPTOR.full_name
        )
        name = label_trait.label if label_trait and label_trait.label else "Lock"

        liveness_trait: weave_heartbeat_pb2.LivenessTrait | None = traits.get(
            weave_heartbeat_pb2.LivenessTrait.DESCRIPTOR.full_name
        )
        online = (
            liveness_trait.status
            == weave_heartbeat_pb2.LivenessTrait.LIVENESS_DEVICE_STATUS_ONLINE
            if liveness_trait
            else True
        )

        battery_trait: weave_power_pb2.BatteryPowerSourceTrait | None = traits.get(
            weave_power_pb2.BatteryPowerSourceTrait.DESCRIPTOR.full_name
        )
        battery_level = 0.0
        battery_voltage = None
        if battery_trait:
            if battery_trait.HasField("remaining") and battery_trait.remaining.HasField(
                "remainingPercent"
            ):
                battery_level = 100 * battery_trait.remaining.remainingPercent.value
            if battery_trait.HasField("assessedVoltage"):
                battery_voltage = battery_trait.assessedVoltage.value

        tamper_trait: weave_security_pb2.TamperTrait | None = traits.get(
            weave_security_pb2.TamperTrait.DESCRIPTOR.full_name
        )
        tampered = (
            tamper_trait.tamperState
            == weave_security_pb2.TamperTrait.TamperState.TAMPER_STATE_TAMPERED
            if tamper_trait
            else False
        )

        settings_trait: weave_security_pb2.BoltLockSettingsTrait | None = traits.get(
            weave_security_pb2.BoltLockSettingsTrait.DESCRIPTOR.full_name
        )
        auto_relock_duration = (
            settings_trait.autoRelockDuration.seconds if settings_trait else 0
        )

        caps_trait: weave_security_pb2.BoltLockCapabilitiesTrait | None = traits.get(
            weave_security_pb2.BoltLockCapabilitiesTrait.DESCRIPTOR.full_name
        )
        max_auto_relock_duration = (
            caps_trait.maxAutoRelockDuration.seconds if caps_trait else 300
        )

        return NestLock(
            object_key=key,
            serial_number=serial_number,
            location=_get_protobuf_location(traits),
            name=name,
            model="Nest x Yale Lock",
            software_version=software_version,
            online=online,
            bolt_state=bolt_state,
            bolt_actor=bolt_actor,
            battery_level=battery_level,
            battery_voltage=battery_voltage,
            tampered=tampered,
            auto_relock_on=settings_trait.autoRelockOn if settings_trait else False,
            auto_relock_duration=auto_relock_duration,
            max_auto_relock_duration=max_auto_relock_duration,
            is_protobuf=True,
        )

    def _parse_proto_targets_and_mode(
        self, traits: dict[str, Any], is_eco_mode: bool
    ) -> tuple[float | None, float | None, float | None, ThermostatHvacMode]:
        """Extract target temperatures and HVAC mode from traits."""
        target_temp = None
        target_low = None
        target_high = None
        hvac_mode = ThermostatHvacMode.OFF

        target_temp_trait: nest_hvac_pb2.TargetTemperatureSettingsTrait | None = (
            traits.get(
                nest_hvac_pb2.TargetTemperatureSettingsTrait.DESCRIPTOR.full_name
            )
        )

        if (
            target_temp_trait
            and target_temp_trait.HasField("enabled")
            and not target_temp_trait.enabled.value
        ):
            return None, None, None, ThermostatHvacMode.OFF

        # Handle Eco Mode Settings to get actual target temps when in Eco
        if is_eco_mode:
            eco_settings: nest_hvac_pb2.EcoModeSettingsTrait | None = traits.get(
                nest_hvac_pb2.EcoModeSettingsTrait.DESCRIPTOR.full_name
            )
            if eco_settings:
                target_low = eco_settings.ecoTemperatureHeat.value.value
                target_high = eco_settings.ecoTemperatureCool.value.value

                # Determine "effective" target based on active flags if available or just overrides
                if (
                    eco_settings.ecoTemperatureHeat.enabled
                    and not eco_settings.ecoTemperatureCool.enabled
                ):
                    target_temp = target_low
                    hvac_mode = ThermostatHvacMode.HEAT
                elif (
                    not eco_settings.ecoTemperatureHeat.enabled
                    and eco_settings.ecoTemperatureCool.enabled
                ):
                    target_temp = target_high
                    hvac_mode = ThermostatHvacMode.COOL
                else:
                    target_temp = (target_low + target_high) / 2
                    hvac_mode = ThermostatHvacMode.RANGE
            return target_temp, target_low, target_high, hvac_mode

        # Standard Target Temperature
        if target_temp_trait and target_temp_trait.HasField("targetTemperature"):
            tt = target_temp_trait.targetTemperature
            if (
                tt.setpointType
                == nest_hvac_pb2.SetPointScheduleSettingsTrait.SetPointType.SET_POINT_TYPE_HEAT
            ):
                target_temp = tt.heatingTarget.value
                hvac_mode = ThermostatHvacMode.HEAT
            elif (
                tt.setpointType
                == nest_hvac_pb2.SetPointScheduleSettingsTrait.SetPointType.SET_POINT_TYPE_COOL
            ):
                target_temp = tt.coolingTarget.value
                hvac_mode = ThermostatHvacMode.COOL
            elif (
                tt.setpointType
                == nest_hvac_pb2.SetPointScheduleSettingsTrait.SetPointType.SET_POINT_TYPE_RANGE
            ):
                target_low = tt.heatingTarget.value
                target_high = tt.coolingTarget.value
                # Calculate middle point for 'target' if needed
                target_temp = (target_low + target_high) / 2
                hvac_mode = ThermostatHvacMode.RANGE

        return target_temp, target_low, target_high, hvac_mode

    def _parse_proto_hvac_state(
        self, hvac_trait: nest_hvac_pb2.HvacControlTrait, fan_state: bool
    ) -> ThermostatHvacState:
        """Determine HVAC action state from traits."""
        hvac_state = ThermostatHvacState.OFF
        if (
            hvac_trait.hvacState.heatStage1Active
            or hvac_trait.hvacState.heatStage2Active
            or hvac_trait.hvacState.heatStage3Active
            or hvac_trait.hvacState.auxiliaryHeatActive
            or hvac_trait.hvacState.emergencyHeatActive
            or hvac_trait.hvacState.alternateHeatStage1Active
            or hvac_trait.hvacState.alternateHeatStage2Active
        ):
            hvac_state = ThermostatHvacState.HEATING
        elif (
            hvac_trait.hvacState.coolStage1Active
            or hvac_trait.hvacState.coolStage2Active
            or hvac_trait.hvacState.coolStage3Active
        ):
            hvac_state = ThermostatHvacState.COOLING
        elif fan_state:
            hvac_state = ThermostatHvacState.FAN
        return hvac_state

    def _parse_proto_fan(
        self, traits: dict[str, Any]
    ) -> tuple[bool, bool, int, int, int, int]:
        """Extract fan capability, state, timer timeout, speed, duration, and max speed."""
        fan_trait: nest_hvac_pb2.FanControlSettingsTrait | None = traits.get(
            nest_hvac_pb2.FanControlSettingsTrait.DESCRIPTOR.full_name
        )
        fan_timer_timeout = (
            fan_trait.timerEnd.ToSeconds()
            if fan_trait and fan_trait.HasField("timerEnd")
            else 0
        )
        fan_state = fan_timer_timeout > time.time()

        fan_timer_speed = 1
        if fan_trait and fan_trait.timerSpeed:
            if (
                fan_trait.timerSpeed
                == nest_hvac_pb2.FanControlTrait.FanSpeedSetting.FAN_SPEED_SETTING_STAGE1
            ):
                fan_timer_speed = 1
            elif (
                fan_trait.timerSpeed
                == nest_hvac_pb2.FanControlTrait.FanSpeedSetting.FAN_SPEED_SETTING_STAGE2
            ):
                fan_timer_speed = 2
            elif (
                fan_trait.timerSpeed
                == nest_hvac_pb2.FanControlTrait.FanSpeedSetting.FAN_SPEED_SETTING_STAGE3
            ):
                fan_timer_speed = 3

        fan_duration = (
            fan_trait.timerDuration.ToSeconds()
            if fan_trait and fan_trait.HasField("timerDuration")
            else 900
        )

        fan_caps_trait: nest_hvac_pb2.FanControlCapabilitiesTrait | None = traits.get(
            nest_hvac_pb2.FanControlCapabilitiesTrait.DESCRIPTOR.full_name
        )
        has_fan = False
        fan_max_speed = 1
        if fan_caps_trait:
            if (
                fan_caps_trait.maxAvailableSpeed
                != nest_hvac_pb2.FanControlTrait.FanSpeedSetting.FAN_SPEED_SETTING_OFF
            ):
                has_fan = True

            if (
                fan_caps_trait.maxAvailableSpeed
                == nest_hvac_pb2.FanControlTrait.FanSpeedSetting.FAN_SPEED_SETTING_STAGE1
            ):
                fan_max_speed = 1
            elif (
                fan_caps_trait.maxAvailableSpeed
                == nest_hvac_pb2.FanControlTrait.FanSpeedSetting.FAN_SPEED_SETTING_STAGE2
            ):
                fan_max_speed = 2
            elif (
                fan_caps_trait.maxAvailableSpeed
                == nest_hvac_pb2.FanControlTrait.FanSpeedSetting.FAN_SPEED_SETTING_STAGE3
            ):
                fan_max_speed = 3
        # Fallback to guessing if capability trait missing
        elif fan_timer_speed > 1:
            fan_max_speed = fan_timer_speed
        elif (
            fan_trait
            and fan_trait.timerSpeed
            == nest_hvac_pb2.FanControlTrait.FanSpeedSetting.FAN_SPEED_SETTING_STAGE3
        ):
            fan_max_speed = 3

        return (
            has_fan,
            fan_state,
            fan_timer_timeout,
            fan_timer_speed,
            fan_duration,
            fan_max_speed,
        )

    def _parse_proto_capabilities(
        self, traits: dict[str, Any]
    ) -> tuple[bool, bool, bool, bool, bool, bool, bool]:
        """Extract HVAC capabilities from traits."""
        capabilities_trait: nest_hvac_pb2.HvacEquipmentCapabilitiesTrait | None = (
            traits.get(
                nest_hvac_pb2.HvacEquipmentCapabilitiesTrait.DESCRIPTOR.full_name
            )
        )
        can_heat = True
        can_cool = True
        has_dehumidifier = False
        has_hot_water_control = False
        has_hot_water_temperature = False
        has_humidifier = False
        has_air_filter = False

        if capabilities_trait:
            can_heat = (
                capabilities_trait.hasStage1Heat
                or capabilities_trait.hasStage2Heat
                or capabilities_trait.hasStage3Heat
            )
            can_cool = (
                capabilities_trait.hasStage1Cool
                or capabilities_trait.hasStage2Cool
                or capabilities_trait.hasStage3Cool
            )
            has_dehumidifier = capabilities_trait.hasDehumidifier
            has_hot_water_control = capabilities_trait.hasHotWaterControl
            has_hot_water_temperature = capabilities_trait.hasHotWaterTemperature
            has_humidifier = capabilities_trait.hasHumidifier
            has_air_filter = capabilities_trait.hasAirFilter

        return (
            can_heat,
            can_cool,
            has_dehumidifier,
            has_hot_water_control,
            has_hot_water_temperature,
            has_humidifier,
            has_air_filter,
        )

    def _parse_proto_hot_water(
        self, traits: dict[str, Any], temp_scale: TemperatureScale | None
    ) -> tuple[
        bool,
        int,
        float | None,
        float | None,
        HotWaterMode,
        bool,
        str | None,
        str | None,
        str | None,
    ]:
        """Extract Hot Water and Heat Link properties from traits."""
        hw_trait: nest_hvac_pb2.HotWaterTrait | None = traits.get(
            nest_hvac_pb2.HotWaterTrait.DESCRIPTOR.full_name
        )
        hw_settings_trait: nest_hvac_pb2.HotWaterSettingsTrait | None = traits.get(
            nest_hvac_pb2.HotWaterSettingsTrait.DESCRIPTOR.full_name
        )

        hot_water_active = False
        hot_water_boost_time_to_end = 0
        hot_water_temperature = None
        current_water_temperature = None
        hot_water_mode = HotWaterMode.OFF
        hot_water_away_enabled = False

        if hw_trait:
            hot_water_active = hw_trait.boilerActive
            if hw_trait.HasField("temperature"):
                current_water_temperature = _round_temp(
                    hw_trait.temperature.value, temp_scale
                )

        if hw_settings_trait:
            if hw_settings_trait.HasField("boostTimerEnd"):
                hot_water_boost_time_to_end = (
                    hw_settings_trait.boostTimerEnd.ToSeconds()
                )
            if hw_settings_trait.HasField("temperature"):
                hot_water_temperature = _round_temp(
                    hw_settings_trait.temperature.value, temp_scale
                )

            if (
                hw_settings_trait.mode
                == nest_hvac_pb2.HotWaterSettingsTrait.HotWaterMode.HOT_WATER_MODE_SCHEDULE
            ):
                hot_water_mode = HotWaterMode.SCHEDULE

            hot_water_away_enabled = hw_settings_trait.structureModeFollowEnabled

        # Heat Link Info
        heat_link_trait: nest_hvac_pb2.HeatLinkTrait | None = traits.get(
            nest_hvac_pb2.HeatLinkTrait.DESCRIPTOR.full_name
        )
        heat_link_serial_number = None
        heat_link_model = None
        heat_link_sw_version = None
        if heat_link_trait:
            if heat_link_trait.HasField("heatLinkSerialNumber"):
                heat_link_serial_number = heat_link_trait.heatLinkSerialNumber.value
            if heat_link_trait.HasField("heatLinkModel"):
                heat_link_model = heat_link_trait.heatLinkModel.value
            if heat_link_trait.HasField("heatLinkSwVersion"):
                heat_link_sw_version = heat_link_trait.heatLinkSwVersion.value

        return (
            hot_water_active,
            hot_water_boost_time_to_end,
            hot_water_temperature,
            current_water_temperature,
            hot_water_mode,
            hot_water_away_enabled,
            heat_link_serial_number,
            heat_link_model,
            heat_link_sw_version,
        )

    def _parse_protobuf_thermostat_model(self, traits: dict[str, Any]) -> str:
        """Determine thermostat model from resource type."""
        resource_type = traits.get("_resource_type")
        if resource_type:
            if resource_type in {
                "nest.resource.NestLearningThermostat3Resource",
                "nest.resource.NestLearningThermostat3v2Resource",
                "nest.resource.NestAmber2DisplayResource",
            }:
                return "Learning Thermostat (3rd gen)"
            if resource_type == "google.resource.GoogleZirconium1Resource":
                return "Thermostat (2020)"
            if resource_type == "google.resource.GoogleBismuth1Resource":
                return "Learning Thermostat (4th gen)"
            if resource_type in {
                "nest.resource.NestOnyxResource",
                "nest.resource.NestAgateDisplayResource",
            }:
                return "Thermostat E"
            if resource_type in {
                "nest.resource.NestLearningThermostat2Resource",
                "nest.resource.NestAmber1DisplayResource",
            }:
                return "Learning Thermostat (2nd gen)"
            if resource_type == "nest.resource.NestLearningThermostat1Resource":
                return "Learning Thermostat (1st gen)"
        return "Thermostat"

    def _parse_protobuf_camera_model(
        self, traits: dict[str, Any], is_doorbell: bool = False
    ) -> str:
        """Determine camera/doorbell model from resource type."""
        resource_type = traits.get("_resource_type")
        if resource_type:
            if resource_type == "google.resource.GreenQuartzResource":
                return "Doorbell (2nd gen, battery)"
            if resource_type == "google.resource.UsticaResource":
                return "Cam Indoor (3rd gen, wired)"
            if resource_type == "google.resource.SpencerResource":
                return "Cam (2nd gen, wired)"
            if resource_type == "google.resource.VenusResource":
                return "Doorbell (2nd gen, wired)"
            if resource_type == "google.resource.RhodesResource":
                return "Doorbell (3rd gen, wired)"
            if resource_type == "nest.resource.NestCamOutdoorResource":
                return "Cam Outdoor (1st gen, wired)"
            if resource_type == "google.resource.LinosaResource":
                return "Cam Outdoor (2nd gen, wired)"
            if resource_type == "nest.resource.NestCamIndoorResource":
                return "Cam Indoor (1st gen)"
            if resource_type == "nest.resource.NestCamIQResource":
                return "Cam IQ Indoor (1st gen)"
            if resource_type == "nest.resource.NestCamIQOutdoorResource":
                return "Cam IQ Outdoor (1st gen, wired)"
            if resource_type == "nest.resource.NestHelloResource":
                return "Doorbell (1st gen, wired)"
            if resource_type in (
                "google.resource.NeonQuartzResource",
                "google.resource.AzizResource",
            ):
                return "Cam with Floodlight (1st gen, wired)"

        return "Doorbell (unknown)" if is_doorbell else "Camera (unknown)"

    def _parse_protobuf_thermostat(
        self, key: str, traits: dict[str, Any], raw_data: dict[str, Any]
    ) -> NestThermostat | None:
        """Parse a Nest Thermostat from protobuf data."""
        hvac_trait: nest_hvac_pb2.HvacControlTrait | None = traits.get(
            nest_hvac_pb2.HvacControlTrait.DESCRIPTOR.full_name
        )
        if not hvac_trait:
            return None

        # Temperature Scale
        display_trait: nest_hvac_pb2.DisplaySettingsTrait | None = traits.get(
            nest_hvac_pb2.DisplaySettingsTrait.DESCRIPTOR.full_name
        )
        temp_scale = TemperatureScale.CELSIUS
        if display_trait:
            try:
                if (
                    display_trait.temperatureScale
                    == nest_hvac_pb2.DisplaySettingsTrait.TemperatureScale.TEMPERATURE_SCALE_F
                ):
                    temp_scale = TemperatureScale.FAHRENHEIT
            except AttributeError:
                pass

        # Identity
        identity_trait: weave_description_pb2.DeviceIdentityTrait | None = traits.get(
            weave_description_pb2.DeviceIdentityTrait.DESCRIPTOR.full_name
        )
        serial_number = identity_trait.serialNumber if identity_trait else key
        software_version = identity_trait.softwareVersion if identity_trait else None

        model = self._parse_protobuf_thermostat_model(traits)

        label_trait: weave_description_pb2.LabelSettingsTrait | None = traits.get(
            weave_description_pb2.LabelSettingsTrait.DESCRIPTOR.full_name
        )
        name = label_trait.label if label_trait and label_trait.label else "Thermostat"

        liveness_trait: weave_heartbeat_pb2.LivenessTrait | None = traits.get(
            weave_heartbeat_pb2.LivenessTrait.DESCRIPTOR.full_name
        )
        online = (
            liveness_trait.status
            == weave_heartbeat_pb2.LivenessTrait.LIVENESS_DEVICE_STATUS_ONLINE
            if liveness_trait
            else True
        )

        # Temperature
        # Prefer the label-specific key to avoid getting backplate_temperature
        # when multiple TemperatureTrait instances exist on the same device.
        temp_trait: nest_sensor_pb2.TemperatureTrait | None = traits.get(
            "current_temperature"
        ) or traits.get(nest_sensor_pb2.TemperatureTrait.DESCRIPTOR.full_name)
        current_temperature = (
            _round_temp(temp_trait.temperatureValue.temperature.value, temp_scale)
            if temp_trait and temp_trait.HasField("temperatureValue")
            else None
        )

        # Backplate temperature (separate TemperatureTrait with label
        # "backplate_temperature", stored under its traitLabel key).
        backplate_temp_trait: nest_sensor_pb2.TemperatureTrait | None = traits.get(
            "backplate_temperature"
        )
        backplate_temperature = (
            _round_temp(
                backplate_temp_trait.temperatureValue.temperature.value, temp_scale
            )
            if backplate_temp_trait
            and backplate_temp_trait.HasField("temperatureValue")
            else None
        )

        # Capabilities (Equipment Capabilities)
        (
            can_heat,
            can_cool,
            has_dehumidifier,
            has_hot_water_control,
            has_hot_water_temperature,
            has_humidifier,
            has_air_filter,
        ) = self._parse_proto_capabilities(traits)

        # Eco Mode
        eco_trait: nest_hvac_pb2.EcoModeStateTrait | None = traits.get(
            nest_hvac_pb2.EcoModeStateTrait.DESCRIPTOR.full_name
        )
        is_eco_mode = (
            eco_trait.ecoMode
            != nest_hvac_pb2.EcoModeStateTrait.EcoMode.ECO_MODE_INACTIVE
            if eco_trait
            else False
        )

        # Target Temperature & Mode (using helper)
        (
            target_temperature,
            target_temperature_low,
            target_temperature_high,
            hvac_mode,
        ) = self._parse_proto_targets_and_mode(traits, is_eco_mode)

        target_temperature = _round_temp(target_temperature, temp_scale)
        target_temperature_low = _round_temp(target_temperature_low, temp_scale)
        target_temperature_high = _round_temp(target_temperature_high, temp_scale)

        # Humidity
        humidity_trait: nest_sensor_pb2.HumidityTrait | None = traits.get(
            nest_sensor_pb2.HumidityTrait.DESCRIPTOR.full_name
        )
        current_humidity = (
            int(humidity_trait.humidityValue.humidity.value)
            if humidity_trait and humidity_trait.HasField("humidityValue")
            else None
        )

        # Dehumidifier / Humidifier / Humidity Control
        humid_ctrl_trait: nest_hvac_pb2.HumidityControlSettingsTrait | None = (
            traits.get(nest_hvac_pb2.HumidityControlSettingsTrait.DESCRIPTOR.full_name)
        )
        dehumidifier_state = False
        humidifier_state = False
        target_humidity = None
        if humid_ctrl_trait:
            if humid_ctrl_trait.HasField("dehumidifierTargetHumidity"):
                dehumidifier_state = humid_ctrl_trait.dehumidifierTargetHumidity.enabled
                target_humidity = humid_ctrl_trait.dehumidifierTargetHumidity.value
            if humid_ctrl_trait.HasField("humidifierTargetHumidity"):
                humidifier_state = humid_ctrl_trait.humidifierTargetHumidity.enabled
                target_humidity = humid_ctrl_trait.humidifierTargetHumidity.value

            # Prefer standard targetHumidity if available
            if humid_ctrl_trait.HasField("targetHumidity"):
                target_humidity = humid_ctrl_trait.targetHumidity.value

        # Fan (using helper)
        (
            has_fan,
            fan_state,
            fan_timer_timeout,
            fan_timer_speed,
            fan_duration,
            fan_max_speed,
        ) = self._parse_proto_fan(traits)

        # HVAC State (using helper)
        hvac_state = self._parse_proto_hvac_state(hvac_trait, fan_state)

        # Temperature Lock Settings
        lock_trait: nest_hvac_pb2.TemperatureLockSettingsTrait | None = traits.get(
            nest_hvac_pb2.TemperatureLockSettingsTrait.DESCRIPTOR.full_name
        )
        temperature_lock = lock_trait.enabled if lock_trait else False

        # Parse Leaf Trait
        leaf_trait: nest_hvac_pb2.LeafTrait | None = traits.get(
            nest_hvac_pb2.LeafTrait.DESCRIPTOR.full_name
        )
        leaf = leaf_trait.active if leaf_trait else False

        # Filter Reminder
        filter_trait: nest_hvac_pb2.FilterReminderTrait | None = traits.get(
            nest_hvac_pb2.FilterReminderTrait.DESCRIPTOR.full_name
        )
        filter_replacement_needed = None
        filter_runtime = None
        if has_air_filter and filter_trait:
            filter_replacement_needed = False
            filter_runtime = 0
            if filter_trait.HasField("filterReplacementNeeded"):
                filter_replacement_needed = filter_trait.filterReplacementNeeded.value
            if filter_trait.HasField("filterRuntime"):
                filter_runtime = filter_trait.filterRuntime.ToSeconds()

        # Hot Water / Heat Link Parsing
        (
            hot_water_active,
            hot_water_boost_time_to_end,
            hot_water_temperature,
            current_water_temperature,
            hot_water_mode,
            hot_water_away_enabled,
            heat_link_serial_number,
            heat_link_model,
            heat_link_sw_version,
        ) = self._parse_proto_hot_water(traits, temp_scale)

        # Battery
        batt_trait: nest_sensor_pb2.BatteryVoltageTrait | None = traits.get(
            nest_sensor_pb2.BatteryVoltageTrait.DESCRIPTOR.full_name
        )
        battery_level = 0.0
        battery_voltage = None
        if batt_trait and batt_trait.HasField("batteryValue"):
            battery_voltage = batt_trait.batteryValue.batteryVoltage.value
            if model == "Thermostat (2020)":
                battery_level = _scale_value(battery_voltage, 2.9, 3.15, 0, 100)
            else:
                battery_level = _scale_value(battery_voltage, 3.6, 3.9, 0, 100)

        # Occupancy
        occupancy = False
        for r_traits in raw_data.values():
            struct_mode = r_traits.get(
                nest_occupancy_pb2.StructureModeTrait.DESCRIPTOR.full_name
            )
            if struct_mode:
                occupancy = (
                    struct_mode.structureMode
                    == nest_occupancy_pb2.StructureModeTrait.StructureMode.STRUCTURE_MODE_HOME
                )
                break

        return NestThermostat(
            object_key=key,
            serial_number=serial_number,
            name=name,
            location=_get_protobuf_location(traits),
            model=model,
            software_version=software_version,
            online=online,
            current_temperature=current_temperature,
            backplate_temperature=backplate_temperature,
            target_temperature=target_temperature,
            target_temperature_low=target_temperature_low,
            target_temperature_high=target_temperature_high,
            current_humidity=current_humidity,
            target_humidity=target_humidity,
            hvac_mode=hvac_mode,
            hvac_state=hvac_state,
            is_eco_mode=is_eco_mode,
            leaf=leaf,
            fan_state=fan_state,
            fan_timer_timeout=fan_timer_timeout,
            fan_timer_speed=fan_timer_speed,
            fan_duration=fan_duration,
            fan_max_speed=fan_max_speed,
            temperature_scale=temp_scale,
            temperature_lock=temperature_lock,
            can_heat=can_heat,
            can_cool=can_cool,
            has_fan=has_fan,
            is_protobuf=True,
            has_hot_water_control=has_hot_water_control,
            has_hot_water_temperature=has_hot_water_temperature,
            heat_link_model=heat_link_model if has_hot_water_control else None,
            heat_link_serial_number=heat_link_serial_number
            if has_hot_water_control
            else None,
            heat_link_sw_version=heat_link_sw_version
            if has_hot_water_control
            else None,
            hot_water_active=hot_water_active,
            hot_water_boost_time_to_end=hot_water_boost_time_to_end,
            hot_water_temperature=hot_water_temperature,
            current_water_temperature=current_water_temperature,
            hot_water_mode=hot_water_mode,
            hot_water_away_enabled=hot_water_away_enabled,
            has_dehumidifier=has_dehumidifier,
            dehumidifier_state=dehumidifier_state,
            has_humidifier=has_humidifier,
            humidifier_state=humidifier_state,
            has_air_filter=has_air_filter,
            filter_replacement_needed=filter_replacement_needed,
            filter_runtime=filter_runtime,
            battery_level=battery_level,
            battery_voltage=battery_voltage,
            occupancy=occupancy,
        )

    def _get_protect_battery(
        self, traits: dict[str, Any]
    ) -> tuple[float, int, float | None]:
        """Calculate battery level and health state."""
        batt_0: nest_sensor_pb2.BatteryVoltageTrait | None = traits.get(
            "battery_voltage_bank0"
        )
        batt_1: nest_sensor_pb2.BatteryVoltageTrait | None = traits.get(
            "battery_voltage_bank1"
        )
        # Fallback to generic descriptor if specific banks not found
        if not batt_0 and not batt_1:
            batt_generic = traits.get(
                nest_sensor_pb2.BatteryVoltageTrait.DESCRIPTOR.full_name
            )
            # Assign to batt_1 to use in level calculation logic below
            batt_1 = batt_generic

        # Calculate battery level (prefer bank1)
        target_batt = batt_1 or batt_0
        battery_level = (
            _milli_volt_to_percentage(
                int(1000 * target_batt.batteryValue.batteryVoltage.value)
            )
            if target_batt
            and target_batt.HasField("batteryValue")
            and target_batt.batteryValue.HasField("batteryVoltage")
            else 0.0
        )

        # Calculate health state: 1 if ANY bank has fault finding, else 0
        battery_health_state = 0
        if (batt_0 and batt_0.HasField("faultInformation")) or (
            batt_1 and batt_1.HasField("faultInformation")
        ):
            battery_health_state = 1

        battery_voltage = None
        if (
            target_batt
            and target_batt.HasField("batteryValue")
            and target_batt.batteryValue.HasField("batteryVoltage")
        ):
            battery_voltage = target_batt.batteryValue.batteryVoltage.value

        return battery_level, battery_health_state, battery_voltage

    def _get_protect_failures(
        self, key: str, traits: dict[str, Any], raw_data: dict[str, Any]
    ) -> set[int]:
        """Extract component failures from SafetySummaryTrait."""
        # --- Parse Component Failures via SafetySummaryTrait ---
        # SafetySummaryTrait is usually on the Structure, not the Device.
        # We search raw_data for any resource that has this trait.
        failures: set[int] = set()
        safety_summary: nest_protect_pb2.SafetySummaryTrait | None = None

        # 1. Check if it's on the device itself (unlikely but possible)
        if nest_protect_pb2.SafetySummaryTrait.DESCRIPTOR.full_name in traits:
            safety_summary = traits[
                nest_protect_pb2.SafetySummaryTrait.DESCRIPTOR.full_name
            ]
        else:
            # 2. Search all other resources (likely the Structure)
            for other_traits in raw_data.values():
                if (
                    nest_protect_pb2.SafetySummaryTrait.DESCRIPTOR.full_name
                    in other_traits
                ):
                    safety_summary = other_traits[
                        nest_protect_pb2.SafetySummaryTrait.DESCRIPTOR.full_name
                    ]
                    # We assume there is only one SafetySummaryTrait (per structure)
                    break

        if safety_summary:
            # Iterate through critical and warning devices to find THIS device (by ID)
            all_statuses = list(safety_summary.criticalDevices) + list(
                safety_summary.warningDevices
            )
            for dev_status in all_statuses:
                # Compare the resourceId in the summary with the current device key
                if dev_status.resourceId.resourceId == key:
                    failures.update(dev_status.failures)

        return failures

    def _get_protect_timestamps(
        self, traits: dict[str, Any], raw_data: dict[str, Any]
    ) -> tuple[int, int]:
        """Get manual and audio self-test timestamps."""
        latest_manual_test_end_utc_secs = 0
        last_audio_self_test_end_utc_secs = 0

        self_test: nest_protect_pb2.SelfTestTrait | None = traits.get(
            nest_protect_pb2.SelfTestTrait.DESCRIPTOR.full_name
        )

        # Check Legacy Structure Trait if device trait missing
        struct_self_test: nest_protect_pb2.LegacyStructureSelfTestTrait | None = None
        if not self_test:
            for other_traits in raw_data.values():
                if (
                    nest_protect_pb2.LegacyStructureSelfTestTrait.DESCRIPTOR.full_name
                    in other_traits
                ):
                    struct_self_test = other_traits[
                        nest_protect_pb2.LegacyStructureSelfTestTrait.DESCRIPTOR.full_name
                    ]
                    break

        if self_test:
            if self_test.HasField("lastMstEnd"):
                latest_manual_test_end_utc_secs = int(self_test.lastMstEnd.ToSeconds())
            if self_test.HasField("lastAstEnd"):
                last_audio_self_test_end_utc_secs = int(
                    self_test.lastAstEnd.ToSeconds()
                )
        elif struct_self_test:
            # Fallback to legacy structure trait
            if struct_self_test.HasField("lastMstEndUtcSecs"):
                latest_manual_test_end_utc_secs = int(
                    struct_self_test.lastMstEndUtcSecs.ToSeconds()
                )
            if struct_self_test.HasField("lastAstEndUtcSecs"):
                last_audio_self_test_end_utc_secs = int(
                    struct_self_test.lastAstEndUtcSecs.ToSeconds()
                )

        return latest_manual_test_end_utc_secs, last_audio_self_test_end_utc_secs

    def _parse_protobuf_protect(
        self, key: str, traits: dict[str, Any], raw_data: dict[str, Any]
    ) -> NestProtect | None:
        """Parse a Nest Protect from protobuf data."""
        smoke_trait: nest_sensor_pb2.SmokeTrait | None = traits.get(
            nest_sensor_pb2.SmokeTrait.DESCRIPTOR.full_name
        )
        co_trait: nest_sensor_pb2.CarbonMonoxideTrait | None = traits.get(
            nest_sensor_pb2.CarbonMonoxideTrait.DESCRIPTOR.full_name
        )
        safety_smoke: nest_safety_pb2.SafetyAlarmSmokeTrait | None = traits.get(
            nest_safety_pb2.SafetyAlarmSmokeTrait.DESCRIPTOR.full_name
        )
        safety_co: nest_safety_pb2.SafetyAlarmCOTrait | None = traits.get(
            nest_safety_pb2.SafetyAlarmCOTrait.DESCRIPTOR.full_name
        )

        if not (smoke_trait or co_trait or safety_smoke or safety_co):
            return None

        identity_trait: weave_description_pb2.DeviceIdentityTrait | None = traits.get(
            weave_description_pb2.DeviceIdentityTrait.DESCRIPTOR.full_name
        )
        serial_number = identity_trait.serialNumber if identity_trait else key
        software_version = identity_trait.softwareVersion if identity_trait else None

        label_trait: weave_description_pb2.LabelSettingsTrait | None = traits.get(
            weave_description_pb2.LabelSettingsTrait.DESCRIPTOR.full_name
        )
        name = (
            label_trait.label if label_trait and label_trait.label else "Nest Protect"
        )

        liveness_trait: weave_heartbeat_pb2.LivenessTrait | None = traits.get(
            weave_heartbeat_pb2.LivenessTrait.DESCRIPTOR.full_name
        )
        online = (
            liveness_trait.status
            == weave_heartbeat_pb2.LivenessTrait.LIVENESS_DEVICE_STATUS_ONLINE
            if liveness_trait
            else True
        )

        battery_level, battery_health_state, battery_voltage = (
            self._get_protect_battery(traits)
        )

        smoke_status = (
            safety_smoke.alarmState
            != nest_safety_pb2.SafetyAlarmTrait.AlarmState.ALARM_STATE_IDLE
            if safety_smoke
            else False
        )
        co_status = (
            safety_co.alarmState
            != nest_safety_pb2.SafetyAlarmTrait.AlarmState.ALARM_STATE_IDLE
            if safety_co
            else False
        )

        # Audio Test Results
        audio_test: nest_protect_pb2.AudioTestTrait | None = traits.get(
            nest_protect_pb2.AudioTestTrait.DESCRIPTOR.full_name
        )
        spk_pass = audio_test.speakerResult.testPassed if audio_test else True
        buz_pass = audio_test.buzzerResult.testPassed if audio_test else True

        failures = self._get_protect_failures(key, traits, raw_data)
        component_smoke_test_passed = (
            nest_protect_pb2.SafetySummaryTrait.FailureType.FAILURE_TYPE_SMOKE
            not in failures
        )
        component_co_test_passed = (
            nest_protect_pb2.SafetySummaryTrait.FailureType.FAILURE_TYPE_CO
            not in failures
        )
        component_hum_test_passed = (
            nest_protect_pb2.SafetySummaryTrait.FailureType.FAILURE_TYPE_HUM
            not in failures
        )
        component_pir_test_passed = (
            nest_protect_pb2.SafetySummaryTrait.FailureType.FAILURE_TYPE_PIR
            not in failures
        )
        component_wifi_test_passed = (
            nest_protect_pb2.SafetySummaryTrait.FailureType.FAILURE_TYPE_WIFI
            not in failures
        )
        component_led_test_passed = (
            nest_protect_pb2.SafetySummaryTrait.FailureType.FAILURE_TYPE_LED
            not in failures
        )

        # Timestamps
        latest_manual_test_end_utc_secs, last_audio_self_test_end_utc_secs = (
            self._get_protect_timestamps(traits, raw_data)
        )

        # --- Replace By Date ---
        replace_by_date = None
        settings: nest_protect_pb2.LegacyProtectDeviceSettingsTrait | None = traits.get(
            nest_protect_pb2.LegacyProtectDeviceSettingsTrait.DESCRIPTOR.full_name
        )
        if settings and settings.HasField("replaceByDate"):
            replace_by_date = datetime.datetime.fromtimestamp(
                settings.replaceByDate.ToSeconds(), datetime.UTC
            ).date()

        legacy_info = traits.get(
            nest_protect_pb2.LegacyProtectDeviceInfoTrait.DESCRIPTOR.full_name
        )

        is_wired = (
            legacy_info.linePowerCapable
            if legacy_info is not None
            else weave_power_pb2.PowerSourceTrait.DESCRIPTOR.full_name in traits
        )

        occupancy = False
        if is_wired:
            occupancy = legacy_info is not None and not legacy_info.autoAway

        enhanced_pathlight: nest_ui_pb2.EnhancedPathlightSettingsTrait | None = (
            traits.get(nest_ui_pb2.EnhancedPathlightSettingsTrait.DESCRIPTOR.full_name)
        )

        night_light_enable = False
        night_light_brightness = None

        if enhanced_pathlight:
            # Enabled if triggers list is not empty
            night_light_enable = bool(enhanced_pathlight.triggers)

            # Map Discrete brightness Enums to Integers (1, 2, 3)
            # LOW=1, MEDIUM=2, HIGH=3
            val = enhanced_pathlight.brightnessDiscrete
            if (
                val
                == nest_ui_pb2.EnhancedPathlightSettingsTrait.PathlightBrightnessDiscrete.PATHLIGHT_BRIGHTNESS_DISCRETE_LOW
            ):
                night_light_brightness = 1
            elif (
                val
                == nest_ui_pb2.EnhancedPathlightSettingsTrait.PathlightBrightnessDiscrete.PATHLIGHT_BRIGHTNESS_DISCRETE_MEDIUM
            ):
                night_light_brightness = 2
            elif (
                val
                == nest_ui_pb2.EnhancedPathlightSettingsTrait.PathlightBrightnessDiscrete.PATHLIGHT_BRIGHTNESS_DISCRETE_HIGH
            ):
                night_light_brightness = 3

        # -- SETTINGS PARSING --
        ntp: nest_protect_pb2.NightTimePromiseSettingsTrait | None = traits.get(
            nest_protect_pb2.NightTimePromiseSettingsTrait.DESCRIPTOR.full_name
        )
        safety_settings: nest_safety_pb2.SafetyAlarmSettingsTrait | None = traits.get(
            nest_safety_pb2.SafetyAlarmSettingsTrait.DESCRIPTOR.full_name
        )

        ntp_green_led_enable = ntp.greenLedEnabled if ntp else False
        heads_up_enable = safety_settings.headsUpEnabled if safety_settings else False
        steam_detection_enable = (
            safety_settings.steamDetectionEnabled if safety_settings else False
        )

        if is_wired:
            return NestWiredProtect(
                object_key=key,
                serial_number=serial_number,
                location=_get_protobuf_location(traits),
                name=name,
                model="Nest Protect (Wired)",
                software_version=software_version,
                online=online,
                smoke_status=smoke_status,
                co_status=co_status,
                battery_level=battery_level,
                battery_voltage=battery_voltage,
                battery_health_state=battery_health_state,
                line_power_present=True,
                occupancy=occupancy,
                night_light_enable=night_light_enable,
                steam_detection_enable=steam_detection_enable,
                night_light_brightness=night_light_brightness,
                component_speaker_test_passed=spk_pass,
                component_smoke_test_passed=component_smoke_test_passed,
                component_co_test_passed=component_co_test_passed,
                component_wifi_test_passed=component_wifi_test_passed,
                component_led_test_passed=component_led_test_passed,
                component_pir_test_passed=component_pir_test_passed,
                component_buzzer_test_passed=buz_pass,
                component_hum_test_passed=component_hum_test_passed,
                ntp_green_led_enable=ntp_green_led_enable,
                heads_up_enable=heads_up_enable,
                replace_by_date=replace_by_date,
                latest_manual_test_end_utc_secs=latest_manual_test_end_utc_secs,
                last_audio_self_test_end_utc_secs=last_audio_self_test_end_utc_secs,
                is_protobuf=True,
            )

        return NestBatteryProtect(
            object_key=key,
            serial_number=serial_number,
            location=_get_protobuf_location(traits),
            name=name,
            model="Nest Protect (Battery)",
            software_version=software_version,
            online=online,
            smoke_status=smoke_status,
            co_status=co_status,
            battery_level=battery_level,
            battery_voltage=battery_voltage,
            battery_health_state=battery_health_state,
            night_light_enable=night_light_enable,
            steam_detection_enable=steam_detection_enable,
            night_light_brightness=night_light_brightness,
            component_speaker_test_passed=spk_pass,
            component_smoke_test_passed=component_smoke_test_passed,
            component_co_test_passed=component_co_test_passed,
            component_wifi_test_passed=component_wifi_test_passed,
            component_led_test_passed=component_led_test_passed,
            component_pir_test_passed=component_pir_test_passed,
            component_buzzer_test_passed=buz_pass,
            component_hum_test_passed=component_hum_test_passed,
            ntp_green_led_enable=ntp_green_led_enable,
            heads_up_enable=heads_up_enable,
            replace_by_date=replace_by_date,
            latest_manual_test_end_utc_secs=latest_manual_test_end_utc_secs,
            last_audio_self_test_end_utc_secs=last_audio_self_test_end_utc_secs,
            is_protobuf=True,
        )

    def _parse_protobuf_camera(
        self, key: str, traits: dict[str, Any]
    ) -> NestCamera | None:
        """Parse a Nest Camera from protobuf data."""
        streaming_trait: nest_camera_pb2.StreamingProtocolTrait | None = traits.get(
            nest_camera_pb2.StreamingProtocolTrait.DESCRIPTOR.full_name
        )
        if not streaming_trait:
            return None

        identity_trait: weave_description_pb2.DeviceIdentityTrait | None = traits.get(
            weave_description_pb2.DeviceIdentityTrait.DESCRIPTOR.full_name
        )
        serial_number = identity_trait.serialNumber if identity_trait else key
        software_version = identity_trait.softwareVersion if identity_trait else None

        label_trait: weave_description_pb2.LabelSettingsTrait | None = traits.get(
            weave_description_pb2.LabelSettingsTrait.DESCRIPTOR.full_name
        )
        name = label_trait.label if label_trait and label_trait.label else "Camera"

        liveness_trait: weave_heartbeat_pb2.LivenessTrait | None = traits.get(
            weave_heartbeat_pb2.LivenessTrait.DESCRIPTOR.full_name
        )
        online = (
            liveness_trait.status
            == weave_heartbeat_pb2.LivenessTrait.LIVENESS_DEVICE_STATUS_ONLINE
            if liveness_trait
            else True
        )

        recording_toggle_trait: nest_camera_pb2.RecordingToggleTrait | None = (
            traits.get(nest_camera_pb2.RecordingToggleTrait.DESCRIPTOR.full_name)
        )
        streaming_enabled = (
            recording_toggle_trait.currentCameraState
            == nest_camera_pb2.CameraState.CAMERA_ON
            if recording_toggle_trait
            else False
        )

        is_streaming = online and streaming_enabled

        # Check MicrophoneSettingsTrait first if available, otherwise guess from capabilities
        mic_trait: nest_audio_pb2.MicrophoneSettingsTrait | None = traits.get(
            nest_audio_pb2.MicrophoneSettingsTrait.DESCRIPTOR.full_name
        )
        if mic_trait:
            audio_enabled = mic_trait.enableMicrophone
        else:
            # Fallback to capability check (imperfect but better than nothing)
            audio_trait: nest_camera_pb2.StreamingProtocolTrait | None = traits.get(
                nest_camera_pb2.StreamingProtocolTrait.DESCRIPTOR.full_name
            )
            audio_enabled = (
                audio_trait.audioCommunicationType
                != nest_camera_pb2.StreamingProtocolTrait.AudioCommunicationType.AUDIO_TYPE_NONE
                if audio_trait
                else False
            )

        indoor_chime_trait: (
            nest_doorbell_pb2.DoorbellIndoorChimeSettingsTrait | None
        ) = traits.get(
            nest_doorbell_pb2.DoorbellIndoorChimeSettingsTrait.DESCRIPTOR.full_name
        )
        indoor_chime_enabled = (
            indoor_chime_trait.chimeEnabled if indoor_chime_trait else False
        )
        has_indoor_chime = False
        if indoor_chime_trait:
            has_indoor_chime = indoor_chime_trait.chimeType in (
                nest_doorbell_pb2.DoorbellIndoorChimeSettingsTrait.ChimeType.CHIME_TYPE_MECHANICAL,
                nest_doorbell_pb2.DoorbellIndoorChimeSettingsTrait.ChimeType.CHIME_TYPE_ELECTRONIC,
            )

        # Snapshot / Live Image URL
        upload_live_image_trait: nest_camera_pb2.UploadLiveImageTrait | None = (
            traits.get(nest_camera_pb2.UploadLiveImageTrait.DESCRIPTOR.full_name)
        )
        nexus_api_http_server_url = (
            upload_live_image_trait.liveImageUrl if upload_live_image_trait else None
        )

        # Battery Level
        battery_trait: weave_power_pb2.BatteryPowerSourceTrait | None = traits.get(
            weave_power_pb2.BatteryPowerSourceTrait.DESCRIPTOR.full_name
        )
        battery_level = None
        battery_voltage = None
        if battery_trait:
            if battery_trait.HasField("assessedVoltage"):
                battery_voltage = battery_trait.assessedVoltage.value
            if battery_trait.HasField("remaining") and battery_trait.remaining.HasField(
                "remainingPercent"
            ):
                battery_level = _scale_value(
                    battery_trait.remaining.remainingPercent.value, 0, 1, 0, 100
                )
            elif battery_voltage:
                voltage_mv = int(battery_voltage * 1000)
                battery_level = _scale_value(voltage_mv, 2000, 3000, 0, 100)

        # Check if it's a doorbell (has doorbell traits)
        is_doorbell = (
            traits.get(
                nest_doorbell_pb2.DoorbellIndoorChimeSettingsTrait.DESCRIPTOR.full_name
            )
            is not None
        )

        model = self._parse_protobuf_camera_model(traits, is_doorbell)

        if is_doorbell:
            return NestDoorbell(
                object_key=key,
                serial_number=serial_number,
                name=name,
                location=_get_protobuf_location(traits),
                model=model,
                software_version=software_version,
                online=online,
                is_streaming=is_streaming,
                streaming_enabled=streaming_enabled,
                audio_enabled=audio_enabled,
                nexus_api_http_server_url=nexus_api_http_server_url
                or "https://nexusapi.dropcam.com",
                web_url=f"https://home.nest.com/camera/{key}",
                indoor_chime_enabled=indoor_chime_enabled,
                has_indoor_chime=has_indoor_chime,
                battery_level=battery_level,
                battery_voltage=battery_voltage,
                is_protobuf=True,
            )

        return NestCamera(
            object_key=key,
            serial_number=serial_number,
            name=name,
            location=_get_protobuf_location(traits),
            model=model,
            software_version=software_version,
            online=online,
            is_streaming=is_streaming,
            streaming_enabled=streaming_enabled,
            audio_enabled=audio_enabled,
            nexus_api_http_server_url=nexus_api_http_server_url
            or "https://nexusapi.dropcam.com",
            web_url=f"https://home.nest.com/camera/{key}",
            battery_level=battery_level,
            battery_voltage=battery_voltage,
            is_protobuf=True,
        )

    def _parse_protobuf_sensor(
        self, key: str, traits: dict[str, Any], raw_data: dict[str, Any]
    ) -> NestTempSensor | None:
        """Parse a Nest Temperature Sensor from protobuf data."""
        # Ensure it's a sensor and not a thermostat (thermostats also have temperature)
        if traits.get(nest_hvac_pb2.HvacControlTrait.DESCRIPTOR.full_name):
            return None

        # Nest Protects have HumidityTrait, but Nest Temperature Sensors (Kryptonite) do not.
        if traits.get(nest_sensor_pb2.HumidityTrait.DESCRIPTOR.full_name):
            return None

        temp_trait: nest_sensor_pb2.TemperatureTrait | None = traits.get(
            nest_sensor_pb2.TemperatureTrait.DESCRIPTOR.full_name
        )
        if not temp_trait:
            return None

        # Determine Active Status by looking at all thermostats in raw_data
        associated_thermostat = None
        is_active = False

        for potential_key, potential_traits in raw_data.items():
            rcs_trait: nest_hvac_pb2.RemoteComfortSensingSettingsTrait | None = (
                potential_traits.get(
                    nest_hvac_pb2.RemoteComfortSensingSettingsTrait.DESCRIPTOR.full_name
                )
            )

            if not rcs_trait:
                continue

            # Check if this sensor is in the associated list of this thermostat
            is_associated = False
            for sensor in rcs_trait.associatedRcsSensors:
                if sensor.deviceId.resourceId == key:
                    is_associated = True
                    break

            if is_associated:
                associated_thermostat = potential_key
                # Check if it is the currently selected active sensor
                if (
                    rcs_trait.activeRcsSelection.rcsSourceType
                    == nest_hvac_pb2.RemoteComfortSensingSettingsTrait.RcsSourceType.RCS_SOURCE_TYPE_SINGLE_SENSOR
                    and rcs_trait.activeRcsSelection.activeRcsSensor.resourceId == key
                ):
                    is_active = True
                break

        temp_scale = TemperatureScale.CELSIUS
        if associated_thermostat and associated_thermostat in raw_data:
            thermostat_traits = raw_data[associated_thermostat]
            display_trait = thermostat_traits.get(
                nest_hvac_pb2.DisplaySettingsTrait.DESCRIPTOR.full_name
            )
            if display_trait:
                try:
                    if (
                        display_trait.temperatureScale
                        == nest_hvac_pb2.DisplaySettingsTrait.TemperatureScale.TEMPERATURE_SCALE_F
                    ):
                        temp_scale = TemperatureScale.FAHRENHEIT
                except AttributeError:
                    pass

        # Identity
        identity_trait: weave_description_pb2.DeviceIdentityTrait | None = traits.get(
            weave_description_pb2.DeviceIdentityTrait.DESCRIPTOR.full_name
        )
        serial_number = identity_trait.serialNumber if identity_trait else key

        label_trait: weave_description_pb2.LabelSettingsTrait | None = traits.get(
            weave_description_pb2.LabelSettingsTrait.DESCRIPTOR.full_name
        )
        name = label_trait.label if label_trait and label_trait.label else "Sensor"

        liveness_trait: weave_heartbeat_pb2.LivenessTrait | None = traits.get(
            weave_heartbeat_pb2.LivenessTrait.DESCRIPTOR.full_name
        )

        beacon_trait: nest_hvac_pb2.KryptoniteObservedBeaconTrait | None = traits.get(
            nest_hvac_pb2.KryptoniteObservedBeaconTrait.DESCRIPTOR.full_name
        )

        if beacon_trait and beacon_trait.HasField("lastBeaconTime"):
            online = (time.time() - beacon_trait.lastBeaconTime.ToSeconds()) < 3600 * 4
        elif liveness_trait:
            online = (
                liveness_trait.status
                == weave_heartbeat_pb2.LivenessTrait.LIVENESS_DEVICE_STATUS_ONLINE
            )
        else:
            online = True

        # Scale battery voltage (2V-3V) to %
        batt_voltage_trait: nest_sensor_pb2.BatteryVoltageTrait | None = traits.get(
            nest_sensor_pb2.BatteryVoltageTrait.DESCRIPTOR.full_name
        )

        battery_level = 0.0
        battery_voltage = None

        if (
            batt_voltage_trait
            and batt_voltage_trait.HasField("batteryValue")
            and batt_voltage_trait.batteryValue.HasField("batteryVoltage")
        ):
            battery_voltage = batt_voltage_trait.batteryValue.batteryVoltage.value
            # Convert V to mV
            voltage_mv = int(battery_voltage * 1000)
            battery_level = _scale_value(voltage_mv, 2000, 3000, 0, 100)
        else:
            # Fallback to remainingPercent
            battery_trait: weave_power_pb2.BatteryPowerSourceTrait | None = traits.get(
                weave_power_pb2.BatteryPowerSourceTrait.DESCRIPTOR.full_name
            )
            if battery_trait:
                if battery_trait.HasField("assessedVoltage"):
                    battery_voltage = battery_trait.assessedVoltage.value

                if battery_trait.HasField(
                    "remaining"
                ) and battery_trait.remaining.HasField("remainingPercent"):
                    battery_level = _scale_value(
                        battery_trait.remaining.remainingPercent.value, 0, 1, 0, 100
                    )
                elif battery_voltage:
                    # Convert V to mV
                    voltage_mv = int(battery_voltage * 1000)
                    battery_level = _scale_value(voltage_mv, 2000, 3000, 0, 100)

        return NestTempSensor(
            object_key=key,
            serial_number=serial_number,
            name=name,
            location=_get_protobuf_location(traits),
            model="Temperature Sensor",
            online=online,
            current_temperature=_round_temp(
                temp_trait.temperatureValue.temperature.value, temp_scale
            ),
            battery_level=battery_level,
            battery_voltage=battery_voltage,
            is_protobuf=True,
            associated_thermostat_object_key=associated_thermostat,
            is_active_sensor=is_active,
        )

    def _parse_protobuf_structure(
        self, key: str, traits: dict[str, Any]
    ) -> NestStructure | None:
        """Parse a Nest Structure from protobuf data."""
        if not traits.get(nest_structure_pb2.StructureInfoTrait.DESCRIPTOR.full_name):
            return None

        # Structure Info
        info_trait: nest_structure_pb2.StructureInfoTrait | None = traits.get(
            nest_structure_pb2.StructureInfoTrait.DESCRIPTOR.full_name
        )
        # Location
        location_trait: nest_structure_pb2.StructureLocationTrait | None = traits.get(
            nest_structure_pb2.StructureLocationTrait.DESCRIPTOR.full_name
        )

        # Identity
        identity_trait: weave_description_pb2.DeviceIdentityTrait | None = traits.get(
            weave_description_pb2.DeviceIdentityTrait.DESCRIPTOR.full_name
        )
        serial_number = (
            identity_trait.serialNumber
            if identity_trait
            else key.rsplit(".", maxsplit=1)[-1]
        )  # Fallback

        # Mode
        mode = StructureMode.HOME
        mode_trait: nest_occupancy_pb2.StructureModeTrait | None = traits.get(
            nest_occupancy_pb2.StructureModeTrait.DESCRIPTOR.full_name
        )
        if mode_trait:
            if (
                mode_trait.structureMode
                == nest_occupancy_pb2.StructureModeTrait.StructureMode.STRUCTURE_MODE_AWAY
            ):
                mode = StructureMode.AWAY
            elif (
                mode_trait.structureMode
                == nest_occupancy_pb2.StructureModeTrait.StructureMode.STRUCTURE_MODE_SLEEP
            ):
                mode = StructureMode.SLEEP
            elif (
                mode_trait.structureMode
                == nest_occupancy_pb2.StructureModeTrait.StructureMode.STRUCTURE_MODE_VACATION
            ):
                mode = StructureMode.VACATION

        return NestStructure(
            object_key=key,
            serial_number=serial_number,
            name=info_trait.name if info_trait else "Home",
            location=location_trait.addressLines[0]
            if location_trait and location_trait.addressLines
            else None,
            mode=mode,
            is_protobuf=True,
        )

    def _create_heatlink(self, thermostat: NestThermostat) -> NestHeatLink | None:
        """Create a virtual Heat Link device from thermostat data."""
        if not (
            thermostat.has_hot_water_control or thermostat.has_hot_water_temperature
        ):
            return None

        raw_model = thermostat.heat_link_model or ""
        if raw_model.startswith("Amber-2"):
            mapped_model = "Heat Link for Learning Thermostat (3rd gen, EU)"
        elif raw_model.startswith("Amber-1"):
            mapped_model = "Heat Link for Learning Thermostat (2nd gen, EU)"
        elif "Agate" in raw_model:
            mapped_model = "Heat Link for Thermostat E (1st gen, EU)"
        elif raw_model:
            mapped_model = f"Heat Link ({raw_model})"
        else:
            mapped_model = "Hot Water Control"

        serial_number = (
            thermostat.heat_link_serial_number
            or f"{thermostat.serial_number}-hot-water"
        )

        return NestHeatLink(
            object_key=f"heatlink.{serial_number}",
            serial_number=serial_number,
            location=thermostat.location,
            name="Heat Link" if thermostat.heat_link_serial_number else "Hot Water",
            model=mapped_model,
            software_version=thermostat.heat_link_sw_version,
            online=thermostat.online,
            associated_thermostat_object_key=thermostat.object_key,
            has_hot_water_control=thermostat.has_hot_water_control,
            hot_water_active=thermostat.hot_water_active,
            has_hot_water_temperature=thermostat.has_hot_water_temperature,
            hot_water_boost_time_to_end=thermostat.hot_water_boost_time_to_end,
            hot_water_mode=thermostat.hot_water_mode,
            hot_water_away_enabled=thermostat.hot_water_away_enabled,
            current_temperature=thermostat.current_water_temperature,
            target_temperature=thermostat.hot_water_temperature,
            temperature_scale=thermostat.temperature_scale,
            is_protobuf=thermostat.is_protobuf,
        )
