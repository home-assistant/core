"""Device metrics helpers."""

from .device_capability import EDeviceCapability, EDeviceType, EFilterState


class DeviceMetric:
    """Class for device metrics helper methods."""

    @staticmethod
    def get_device_type(data: dict) -> str | None:
        """Get device type."""
        return data.get("deviceType", {}).get("childType", {}).get("name")

    @staticmethod
    def get_power_state(data: dict) -> bool:
        """Get power state."""
        if not data:
            return False

        device_type_name = DeviceMetric.get_device_type(data)
        if device_type_name == EDeviceType.HEATPUMP.value:
            return (
                data.get("pumpAdditionalItems", {}).get("state", {}).get("pow") == "on"
            )
        return data.get("isEnabled", False)

    @staticmethod
    def get_capability_value(data: dict, capability: EDeviceCapability):  # noqa: C901
        """Get capability value."""
        if not data:
            return None

        reported = data.get("deviceSettings", {}).get("reported", {})
        metrics = data.get("lastMetrics", {})
        data.get("airPurifierDefaultSettings", {})

        if capability == EDeviceCapability.ONOFF:
            return DeviceMetric.get_power_state(data)
        if capability == EDeviceCapability.TARGET_TEMPERATURE:
            return reported.get("temperature_normal")
        if capability == EDeviceCapability.MEASURE_TEMPERATURE:
            return metrics.get("temperatureAmbient") or metrics.get("temperature")
        if capability == EDeviceCapability.MEASURE_HUMIDITY:
            return metrics.get("humidity")
        if capability == EDeviceCapability.MEASURE_POWER:
            return metrics.get("currentPower") or 0
        if capability == EDeviceCapability.MEASURE_DAILY_POWER:
            return (
                data.get("energyUsageForCurrentDay")
                or data.get("getDeviceEnergyUsageDaily")
                or metrics.get("energyUsageForCurrentDay")
                or 0
            )
        if capability == EDeviceCapability.INDIVIDUAL_CONTROL:
            return reported.get("operation_mode") == "control_individually"
        if capability == EDeviceCapability.CHILD_LOCK:
            return reported.get("lock_status") == "child"
        if capability == EDeviceCapability.COMMERCIAL_LOCK:
            return reported.get("lock_status") == "commercial"
        if capability == EDeviceCapability.OPEN_WINDOW:
            return reported.get("open_window", {}).get("enabled", False)
        if capability == EDeviceCapability.PREDICTIVE_HEATING:
            return reported.get("predictive_heating_type") == "advanced"
        if capability == EDeviceCapability.PID_CONTROLLER:
            return reported.get("regulator_type") == "pid"
        if capability == EDeviceCapability.SLOW_PID:
            return reported.get("regulator_type") == "hysteresis_or_slow_pid"
        if capability == EDeviceCapability.COOLING_MODE:
            return reported.get("additional_socket_mode") == "cooling"
        if capability == EDeviceCapability.ADJUST_WATTAGE:
            return reported.get("limited_heating_power")
        if capability == EDeviceCapability.MEASURE_WATTAGE:
            return reported.get("max_heater_power")

        if capability == EDeviceCapability.MEASURE_CO2:
            return metrics.get("eco2")
        if capability == EDeviceCapability.MEASURE_TVOC:
            return metrics.get("tvoc")
        if capability == EDeviceCapability.MEASURE_BATTERY:
            return metrics.get("batteryPercentage")

        if capability == EDeviceCapability.MEASURE_PM1:
            return metrics.get("massPm_10")
        if capability == EDeviceCapability.MEASURE_PM25:
            return metrics.get("massPm_25")
        if capability == EDeviceCapability.MEASURE_PM10:
            return metrics.get("massPm_100")
        if capability == EDeviceCapability.MEASURE_PARTICLES:
            pm1_raw = metrics.get("massPm_10")
            pm25_raw = metrics.get("massPm_25")
            pm10_raw = metrics.get("massPm_100")

            values_for_sum = []
            all_values_valid_and_present = True

            for val_raw in [pm1_raw, pm25_raw, pm10_raw]:
                if val_raw is None:
                    all_values_valid_and_present = False
                    break
                try:
                    values_for_sum.append(float(val_raw))
                except (ValueError, TypeError):
                    all_values_valid_and_present = False
                    break

            if all_values_valid_and_present:
                average = sum(values_for_sum) / 3.0
                return round(average, 2)
            else:  # noqa: RET505
                return 0.0

        if capability == EDeviceCapability.MEASURE_FILTER_STATE:
            return reported.get("filter_state") or EFilterState.UNKNOWN.value

        if capability == EDeviceCapability.PURIFIER_MODE:
            return reported.get("fan_speed_mode")

        return None
