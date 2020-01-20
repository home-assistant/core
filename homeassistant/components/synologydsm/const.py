"""Constants for Synology DSM."""
DOMAIN = "synologydsm"
SERVICE_UPDATE = f"{DOMAIN}_update"

CONF_VOLUMES = "volumes"
DEFAULT_NAME = "Synology DSM"
DEFAULT_SSL = True
DEFAULT_PORT = 5000
DEFAULT_PORT_SSL = 5001
DEFAULT_DSM_VERSION = 6

UTILISATION_MON_COND = {
    "cpu_other_load": ["CPU Load (Other)", "%", "mdi:chip"],
    "cpu_user_load": ["CPU Load (User)", "%", "mdi:chip"],
    "cpu_system_load": ["CPU Load (System)", "%", "mdi:chip"],
    "cpu_total_load": ["CPU Load (Total)", "%", "mdi:chip"],
    "cpu_1min_load": ["CPU Load (1 min)", "%", "mdi:chip"],
    "cpu_5min_load": ["CPU Load (5 min)", "%", "mdi:chip"],
    "cpu_15min_load": ["CPU Load (15 min)", "%", "mdi:chip"],
    "memory_real_usage": ["Memory Usage (Real)", "%", "mdi:memory"],
    "memory_size": ["Memory Size", "Mb", "mdi:memory"],
    "memory_cached": ["Memory Cached", "Mb", "mdi:memory"],
    "memory_available_swap": ["Memory Available (Swap)", "Mb", "mdi:memory"],
    "memory_available_real": ["Memory Available (Real)", "Mb", "mdi:memory"],
    "memory_total_swap": ["Memory Total (Swap)", "Mb", "mdi:memory"],
    "memory_total_real": ["Memory Total (Real)", "Mb", "mdi:memory"],
    "network_up": ["Network Up", "Kbps", "mdi:upload"],
    "network_down": ["Network Down", "Kbps", "mdi:download"],
}
STORAGE_VOL_MON_COND = {
    "volume_status": ["Status", None, "mdi:checkbox-marked-circle-outline"],
    "volume_device_type": ["Type", None, "mdi:harddisk"],
    "volume_size_total": ["Total Size", None, "mdi:chart-pie"],
    "volume_size_used": ["Used Space", None, "mdi:chart-pie"],
    "volume_percentage_used": ["Volume Used", "%", "mdi:chart-pie"],
    "volume_disk_temp_avg": ["Average Disk Temp", None, "mdi:thermometer"],
    "volume_disk_temp_max": ["Maximum Disk Temp", None, "mdi:thermometer"],
}
STORAGE_DSK_MON_COND = {
    "disk_name": ["Name", None, "mdi:harddisk"],
    "disk_device": ["Device", None, "mdi:dots-horizontal"],
    "disk_smart_status": ["Status (Smart)", None, "mdi:checkbox-marked-circle-outline"],
    "disk_status": ["Status", None, "mdi:checkbox-marked-circle-outline"],
    "disk_exceed_bad_sector_thr": ["Exceeded Max Bad Sectors", None, "mdi:test-tube"],
    "disk_below_remain_life_thr": ["Below Min Remaining Life", None, "mdi:test-tube"],
    "disk_temp": ["Temperature", None, "mdi:thermometer"],
}

MONITORED_CONDITIONS = (
    list(UTILISATION_MON_COND.keys())
    + list(STORAGE_VOL_MON_COND.keys())
    + list(STORAGE_DSK_MON_COND.keys())
)

MEMORY_SENSORS_KEYS = [
    "memory_size",
    "memory_cached",
    "memory_available_swap",
    "memory_available_real",
    "memory_total_swap",
    "memory_total_real",
]
NETWORK_SENSORS_KEYS = ["network_up", "network_down"]
TEMP_SENSORS_KEYS = ["volume_disk_temp_avg", "volume_disk_temp_max", "disk_temp"]
