"""Constants used by the TrueNAS integration."""

from homeassistant.const import Platform

PLATFORMS = [
    Platform.SENSOR,
]

DOMAIN = "truenas_ce"
# Domain of the original (pre-rename) integration. While DOMAIN equals
# LEGACY_DOMAIN the Community-Edition migration is inert; once DOMAIN is renamed
# to "truenas_ce" the migration adopts the entities/history left behind by the
# old "truenas" integration. See migration.py.
LEGACY_DOMAIN = "truenas"
DEFAULT_NAME = "root"
ATTRIBUTION = "Data provided by TrueNAS integration"

# Dispatcher signal used to (re)discover entities on each coordinator refresh.
SIGNAL_UPDATE_SENSORS = "update_sensors"

# TrueNAS interface link states (from interface.query -> state/link_state).
LINK_STATE_UP = "LINK_STATE_UP"
LINK_STATE_DOWN = "LINK_STATE_DOWN"

DEFAULT_HOST = "truenas.local"

# Conversion factor: kilobits per second to kibibytes per second
# (1000 / 8192 = ~0.12207)
KILOBITS_TO_KIBIBYTES_FACTOR = 0.12207

# Tolerance in seconds to prevent Uptime sensor fluctuations
UPTIME_EPOCH_TOLERANCE_SECONDS = 300

# Default per-query timeout in seconds
QUERY_TIMEOUT: float = 30.0

# Error constants
ERR_CERT_VERIFY_FAILED = "certificate_verify_failed"
ERR_HTTP_USED = "http_used"
ERR_TLS_NOT_SUPPORTED = "tlsv1_not_supported"
ERR_WS_NOT_SUPPORTED = "websocket_not_supported"
ERR_UNKNOWN_HOSTNAME = "unknown_hostname"
ERR_CONNECTION_REFUSED = "connection_refused"
ERR_INVALID_HOSTNAME = "invalid_hostname"
ERR_HANDSHAKE_TIMEOUT = "handshake_timeout"
ERR_INVALID_KEY = "invalid_key"
ERR_PROXY_INTERCEPTED = "proxy_intercepted"
ERR_API_NOT_FOUND = "api_not_found"
ERR_TIMEOUT = "timeout"
ERR_MALFORMED_RESULT = "malformed_result"
ERR_LOST_LOGIN = "connection_lost_mid_login"
ERR_LOST_QUERY = "connection_lost_mid_query"
ERR_UNKNOWN = "unknown_error"

# need for ha ip dns validation, to avoid false positives
KNOWN_DOMAINS = [
    "fritz.box",
    "local",
    "lan",
    "home",
    "speedport.ip",
    "tplinkwifi.net",
    "home.arpa",
    "mshome.net",
    "internal",
]

DEFAULT_DEVICE_NAME = "TrueNAS"
DEFAULT_SSL_VERIFY = False
DEFAULT_CRONJOB_SKIP_DISABLED = True
DEFAULT_DATA_UNIT = "GiB"
ALLOWED_DATA_UNITS = ["GB", "GiB"]

TO_REDACT = {
    "password",
    "passphrase",
    "encryption_password",
    "encryption_salt",
    "host",
    "api_key",
    "serial",
    "system_serial",
    "ip4_addr",
    "ip6_addr",
    "account",
    "key",
    "certificate",
    "privatekey",
    "dataset_passphrases",
}

CONF_CRONJOB_SKIP_DISABLED = "cronjob_skip_disabled"
CONF_DATA_UNIT = "data_unit"

# Stable per-installation identifier (``system.global.id``, a 128-bit UUID),
# recorded on every successful connection test. Lets a later zeroconf
# rediscovery of the same physical box under a new IP be told apart from an
# unrelated device, without needing any pre-authentication probe for it.
CONF_SYSTEM_ID = "system_id"

# Community-Edition migration rollback. Raises a fixable Repairs issue on
# demand — the issue is NOT shown automatically after the migration. Dismissing
# it just closes it.
ISSUE_MIGRATION_ROLLBACK = "migration_rollback_available"

# Community-Edition migration state, persisted on the (new) config entry's data.
# MIGRATION_DONE is the idempotency flag; MIGRATION_RECORDS holds the complete,
# never-pruned reverse map (unique_id -> old entity_id + registry overrides) so
# the adoption can always be fully rolled back; MIGRATION_RESOLVED_UNIQUE_IDS
# tracks which of those records have already reclaimed their id, so retries of
# the still-pending ones (see pending_legacy_records) never revisit a resolved
# record and fight a user's later manual rename; MIGRATION_LEGACY_ENTRY_ID/​
# _CONFIG remember the disabled legacy entry and a snapshot of its data+options
# for a clean rollback; MIGRATION_BACKUP_KEY is the .storage key of the
# standalone safety snapshot. See migration.py.
MIGRATION_DONE = "ce_migration_done"
MIGRATION_RECORDS = "ce_migration_records"
MIGRATION_RESOLVED_UNIQUE_IDS = "ce_migration_resolved_unique_ids"
MIGRATION_LEGACY_ENTRY_ID = "ce_migration_legacy_entry_id"
MIGRATION_LEGACY_CONFIG = "ce_migration_legacy_config"
MIGRATION_BACKUP_KEY = "ce_migration_backup_key"

# Options-Flow
CONF_POLL_INTERVAL = "poll_interval"
DEFAULT_POLL_INTERVAL = 60
ALLOWED_POLL_INTERVALS = ["5", "10", "30", "60", "120", "300"]

CONF_BEHAVIORS = "behaviors"
BEHAVIOR_SKIP_DISABLED_CRONJOBS = "skip_disabled_cronjobs"
BEHAVIOR_REMOVE_INACTIVE_NIC = "remove_inactive_nic"
DEFAULT_BEHAVIORS = [BEHAVIOR_SKIP_DISABLED_CRONJOBS]

CONF_MONITORED_GROUPS = "monitored_groups"
MONITOR_GROUP_UPS = "ups"
MONITOR_GROUP_VMS = "vms"
MONITOR_GROUP_CONTAINERS = "containers"
MONITOR_GROUP_CLOUDSYNC = "cloudsync"
MONITOR_GROUP_REPLICATION = "replication"
MONITOR_GROUP_RSYNC = "rsync"
MONITOR_GROUP_SNAPSHOTS = "snapshots"
MONITOR_GROUP_CRONJOBS = "cronjobs"
MONITOR_GROUP_DATASETS = "datasets"
MONITOR_GROUP_DIRECTORY_SERVICES = "directory_services"
DEFAULT_MONITORED_GROUPS = [
    MONITOR_GROUP_UPS,
    MONITOR_GROUP_VMS,
    MONITOR_GROUP_CONTAINERS,
    MONITOR_GROUP_CLOUDSYNC,
    MONITOR_GROUP_REPLICATION,
    MONITOR_GROUP_RSYNC,
    MONITOR_GROUP_SNAPSHOTS,
    MONITOR_GROUP_CRONJOBS,
    MONITOR_GROUP_DATASETS,
    MONITOR_GROUP_DIRECTORY_SERVICES,
]

ERROR_API_FORMAT = "TrueNAS %s API error: %s"
