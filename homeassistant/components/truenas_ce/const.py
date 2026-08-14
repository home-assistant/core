"""Constants used by the TrueNAS integration."""

import voluptuous as vol
from homeassistant.const import Platform
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import VolDictType

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

DEFAULT_HOST = "trueas.local"

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

# Config-entry data key for the per-dataset stored passphrases dict.
CONF_DATASET_PASSPHRASES = "dataset_passphrases"  # nosec B105 # NOSONAR

SERVICE_CLOUDSYNC_RUN = "cloudsync_run"
SCHEMA_SERVICE_CLOUDSYNC_RUN: VolDictType = {}

SERVICE_CLOUDSYNC_ABORT = "cloudsync_abort"
SCHEMA_SERVICE_CLOUDSYNC_ABORT: VolDictType = {}

SERVICE_RSYNC_RUN = "rsync_run"
SCHEMA_SERVICE_RSYNC_RUN: VolDictType = {}

SERVICE_REPLICATION_RUN = "replication_run"
SCHEMA_SERVICE_REPLICATION_RUN: VolDictType = {}

SERVICE_DATASET_SNAPSHOT = "dataset_snapshot"
SCHEMA_SERVICE_DATASET_SNAPSHOT: VolDictType = {}

SERVICE_DATASET_LOCK = "dataset_lock"
SERVICE_DATASET_UNLOCK = "dataset_unlock"
# B105 false positive: this is the service *field name*, not a hardcoded secret.
SERVICE_DATASET_UNLOCK_PASSPHRASE = "passphrase"  # nosec B105
SERVICE_DATASET_LOCK_FORCE_UMOUNT = "force_umount"
SERVICE_DATASET_UNLOCK_RECURSIVE = "recursive"
SERVICE_DATASET_UNLOCK_FORCE = "force"
SCHEMA_SERVICE_DATASET_LOCK = {
    vol.Required(SERVICE_DATASET_LOCK_FORCE_UMOUNT, default=False): cv.boolean,
}
SCHEMA_SERVICE_DATASET_UNLOCK = {
    vol.Optional(SERVICE_DATASET_UNLOCK_PASSPHRASE): cv.string,
    vol.Required(SERVICE_DATASET_UNLOCK_RECURSIVE, default=False): cv.boolean,
    vol.Required(SERVICE_DATASET_UNLOCK_FORCE, default=False): cv.boolean,
}

# Shared field name used in service call.data to select a specific config entry.
SERVICE_CONFIG_ENTRY = "config_entry"

# B105/S2068 false positive: these are service *name* strings, not hardcoded secrets.
SERVICE_PASSPHRASE_SET = "passphrase_set"  # nosec B105 # NOSONAR
SERVICE_PASSPHRASE_REMOVE = "passphrase_remove"  # nosec B105 # NOSONAR
SERVICE_PASSPHRASE_DATASET_PATH = "dataset_path"  # nosec B105 # NOSONAR
SCHEMA_SERVICE_PASSPHRASE_SET = {
    vol.Required(SERVICE_DATASET_UNLOCK_PASSPHRASE): cv.string,
}
SCHEMA_SERVICE_PASSPHRASE_REMOVE = vol.Schema(
    {
        vol.Optional(SERVICE_CONFIG_ENTRY): cv.string,
        vol.Required(SERVICE_PASSPHRASE_DATASET_PATH): cv.string,
    }
)
SERVICE_PASSPHRASE_LIST = "passphrase_list"  # nosec B105 # NOSONAR
SCHEMA_SERVICE_PASSPHRASE_LIST = vol.Schema(
    {
        vol.Optional(SERVICE_CONFIG_ENTRY): cv.string,
    }
)

SERVICE_SNAPSHOTTASK_RUN = "snapshottask_run"
SCHEMA_SERVICE_SNAPSHOTTASK_RUN: VolDictType = {}

# JSON-RPC methods for on-demand "run" triggers, shared by the run buttons
# (button_types.py) and the *_run sensor actions (sensor.py) so the method name
# is defined once.
API_CLOUDSYNC_SYNC = "cloudsync.sync"
API_CRONJOB_RUN = "cronjob.run"
API_RSYNCTASK_RUN = "rsynctask.run"
API_REPLICATION_RUN = "replication.run"
API_SNAPSHOTTASK_RUN = "pool.snapshottask.run"
API_POOL_SCRUB_SCRUB = "pool.scrub.scrub"
SCRUB_ACTION_START = "START"

SERVICE_SYSTEM_REBOOT = "system_reboot"
SCHEMA_SERVICE_SYSTEM_REBOOT: VolDictType = {}

SERVICE_SYSTEM_SHUTDOWN = "system_shutdown"
SCHEMA_SERVICE_SYSTEM_SHUTDOWN: VolDictType = {}

SERVICE_SYSTEM_REFRESH = "system_refresh"
SCHEMA_SERVICE_SYSTEM_REFRESH: VolDictType = {}

SERVICE_ALERT_DISMISS = "alert_dismiss"
SERVICE_ALERT_RESTORE = "alert_restore"
SERVICE_ALERT_LIST = "alert_list"
SERVICE_ALERT_UUID = "uuid"
SERVICE_ALERT_CONFIG_ENTRY = "config_entry"
SERVICE_ALERT_PROPERTIES = "properties"
DEFAULT_ALERT_PROPERTIES = "uuid,formatted"
SCHEMA_SERVICE_ALERT_DISMISS = vol.Schema(
    {
        vol.Optional(SERVICE_ALERT_CONFIG_ENTRY): cv.string,
        vol.Required(SERVICE_ALERT_UUID): cv.string,
    }
)
SCHEMA_SERVICE_ALERT_RESTORE = vol.Schema(
    {
        vol.Optional(SERVICE_ALERT_CONFIG_ENTRY): cv.string,
        vol.Required(SERVICE_ALERT_UUID): cv.string,
    }
)
SCHEMA_SERVICE_ALERT_LIST = vol.Schema(
    {
        vol.Optional(SERVICE_ALERT_CONFIG_ENTRY): cv.string,
        vol.Optional(
            SERVICE_ALERT_PROPERTIES, default=DEFAULT_ALERT_PROPERTIES
        ): cv.string,
    }
)

CONF_CRONJOB_SKIP_DISABLED = "cronjob_skip_disabled"
CONF_DATA_UNIT = "data_unit"

# Stable per-installation identifier (``system.global.id``, a 128-bit UUID),
# recorded on every successful connection test. Lets a later zeroconf
# rediscovery of the same physical box under a new IP be told apart from an
# unrelated device, without needing any pre-authentication probe for it.
CONF_SYSTEM_ID = "system_id"

# Orphaned long-term statistics cleanup (Repairs issue + diagnostic button).
CONF_STATISTICS_CLEANUP_IGNORED = "statistics_cleanup_ignored"
ISSUE_STATISTICS_ORPHANED = "statistics_orphaned"
BUTTON_STATISTICS_CLEANUP = "statistics_cleanup"

# Diagnostic button that forces an immediate coordinator re-poll (same effect as
# the system_refresh action), so the data can be refreshed on demand from the UI.
BUTTON_SYSTEM_REFRESH = "system_refresh"

# Community-Edition migration rollback. A diagnostic button (safe: it only opens a
# Repairs confirm dialog, it never rolls back directly) raises a fixable Repairs
# issue on demand — the issue is NOT shown automatically after the migration.
# Dismissing it just closes it; pressing the button again re-raises it.
BUTTON_MIGRATION_ROLLBACK = "migration_rollback"
ISSUE_MIGRATION_ROLLBACK = "migration_rollback_available"

# Community-Edition migration state, persisted on the (new) config entry's data.
# MIGRATION_DONE is the idempotency flag; MIGRATION_RECORDS holds the reverse map
# (unique_id -> old entity_id + registry overrides) so the adoption can be rolled
# back; MIGRATION_LEGACY_ENTRY_ID/​_CONFIG remember the disabled legacy entry and
# a snapshot of its data+options for a clean rollback; MIGRATION_BACKUP_KEY is the
# .storage key of the standalone safety snapshot. See migration.py.
MIGRATION_DONE = "ce_migration_done"
MIGRATION_RECORDS = "ce_migration_records"
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

# Maps each monitored-group option key to the coordinator ds data_path(s) it owns.
# Used by the orphan-cleanup to force-remove entities when a group is disabled.
GROUP_DATA_PATHS: dict[str, set[str]] = {
    MONITOR_GROUP_UPS: {"ups"},
    MONITOR_GROUP_VMS: {"vm"},
    MONITOR_GROUP_CONTAINERS: {"container"},
    MONITOR_GROUP_CLOUDSYNC: {"cloudsync"},
    MONITOR_GROUP_REPLICATION: {"replication"},
    MONITOR_GROUP_RSYNC: {"rsynctask"},
    MONITOR_GROUP_SNAPSHOTS: {"snapshottask"},
    MONITOR_GROUP_CRONJOBS: {"cronjob"},
    MONITOR_GROUP_DATASETS: {"dataset"},
    MONITOR_GROUP_DIRECTORY_SERVICES: {"directoryservices"},
}

ERROR_API_FORMAT = "TrueNAS %s API error: %s"
