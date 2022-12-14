"""Constants for the Nextcloud integration."""
from datetime import timedelta

DOMAIN = "nextcloud"

DEFAULT_NAME = "Nextcloud"
SCAN_INTERVAL = timedelta(seconds=60)

DATA_KEY_API = "api"
DATA_KEY_COORDINATOR = "coordinator"

BINARY_SENSORS = (
    "system_enable_avatars",
    "system_enable_previews",
    "system_filelocking.enabled",
    "system_debug",
)

SENSORS = (
    "system_version",
    "system_theme",
    "system_memcache.local",
    "system_memcache.distributed",
    "system_memcache.locking",
    "system_freespace",
    "system_cpuload",
    "system_mem_total",
    "system_mem_free",
    "system_swap_total",
    "system_swap_free",
    "system_apps_num_installed",
    "system_apps_num_updates_available",
    "system_apps_app_updates_calendar",
    "system_apps_app_updates_contacts",
    "system_apps_app_updates_tasks",
    "system_apps_app_updates_twofactor_totp",
    "storage_num_users",
    "storage_num_files",
    "storage_num_storages",
    "storage_num_storages_local",
    "storage_num_storages_home",
    "storage_num_storages_other",
    "shares_num_shares",
    "shares_num_shares_user",
    "shares_num_shares_groups",
    "shares_num_shares_link",
    "shares_num_shares_mail",
    "shares_num_shares_room",
    "shares_num_shares_link_no_password",
    "shares_num_fed_shares_sent",
    "shares_num_fed_shares_received",
    "shares_permissions_3_1",
    "server_webserver",
    "server_php_version",
    "server_php_memory_limit",
    "server_php_max_execution_time",
    "server_php_upload_max_filesize",
    "database_type",
    "database_version",
    "activeUsers_last5minutes",
    "activeUsers_last1hour",
    "activeUsers_last24hours",
)
