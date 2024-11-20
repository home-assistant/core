"""Constants for System Monitor."""

DOMAIN = "systemmonitor"

CONF_INDEX = "index"
CONF_PROCESS = "process"

NET_IO_TYPES = [
    "network_in",
    "network_out",
    "throughput_network_in",
    "throughput_network_out",
    "packets_in",
    "packets_out",
]

# There might be additional keys to be added for different
# platforms / hardware combinations.
# Taken from last version of "glances" integration before they moved to
# a generic temperature sensor logic.
# https://github.com/home-assistant/core/blob/5e15675593ba94a2c11f9f929cdad317e27ce190/homeassistant/components/glances/sensor.py#L199
CPU_SENSOR_PREFIXES = [
    "amdgpu 1",
    "aml_thermal",
    "Core 0",
    "Core 1",
    "CPU Temperature",
    "CPU",
    "cpu-thermal 1",
    "cpu_thermal 1",
    "exynos-therm 1",
    "Package id 0",
    "Physical id 0",
    "radeon 1",
    "soc-thermal 1",
    "soc_thermal 1",
    "Tctl",
    "cpu0-thermal",
    "cpu0_thermal",
    "k10temp 1",
]
