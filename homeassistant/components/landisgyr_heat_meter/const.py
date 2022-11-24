"""Constants for the Landis+Gyr Heat Meter integration."""

from datetime import timedelta

DOMAIN = "landisgyr_heat_meter"

ULTRAHEAT_TIMEOUT = 30  # reading the IR port can take some time
POLLING_INTERVAL = timedelta(days=1)  # Polling is only daily to prevent battery drain.


# Translation table between intern key and key used for API
API_KEY = {
    "heat_usage": "heat_usage_mwh",
    "volume_usage_m3": "volume_usage_m3",
    "heat_usage_gj": "heat_usage_gj",
    "heat_previous_year": "heat_previous_year_mwh",
    "heat_previous_year_gj": "heat_previous_year_gj",
    "volume_previous_year_m3": "volume_previous_year_m3",
    "ownership_number": "ownership_number",
    "error_number": "error_number",
    "device_number": "device_number",
    "measurement_period_minutes": "measurement_period_minutes",
    "power_max_kw": "power_max_kw",
    "power_max_previous_year_kw": "power_max_previous_year_kw",
    "flowrate_max_m3ph": "flowrate_max_m3ph",
    "flowrate_max_previous_year_m3ph": "flowrate_max_previous_year_m3ph",
    "return_temperature_max_c": "return_temperature_max_c",
    "return_temperature_max_previous_year_c": "return_temperature_max_previous_year_c",
    "flow_temperature_max_c": "flow_temperature_max_c",
    "flow_temperature_max_previous_year_c": "flow_temperature_max_previous_year_c",
    "operating_hours": "operating_hours",
    "flow_hours": "flow_hours",
    "fault_hours": "fault_hours",
    "fault_hours_previous_year": "fault_hours_previous_year",
    "yearly_set_day": "yearly_set_day",
    "monthly_set_day": "monthly_set_day",
    "meter_date_time": "meter_date_time",
    "measuring_range_m3ph": "measuring_range_m3ph",
    "settings_and_firmware": "settings_and_firmware",
}

MWH_ONLY_KEYS = ["heat_usage", "heat_previous_year"]
GJ_ONLY_KEYS = ["heat_usage_gj", "heat_previous_year_gj"]
