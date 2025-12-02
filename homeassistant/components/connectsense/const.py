from datetime import timedelta

DOMAIN = "connectsense"

# Dispatcher signal base; we suffix with entry_id so multiple devices don't cross-talk
SIGNAL_UPDATE = "connectsense_update"

# ---- Options (user notifications) ----
CONF_NOTIFY_ENABLED = "notify_enabled"          # bool
CONF_NOTIFY_SERVICE = "notify_service"          # e.g. "notify.notify" (default) or "notify.mobile_app_..."
CONF_NOTIFY_CODE_OFF = "notify_on_off"          # bool
CONF_NOTIFY_CODE_ON = "notify_on_on"            # bool
CONF_NOTIFY_CODE_REBOOT = "notify_on_reboot"    # bool

# Rebooter Pro notification codes
CODE_OFF = 1
CODE_ON = 2
CODE_REBOOTING = 3

# Token-based webhook auth (HTTP, plaintext shared secret)
CONF_WEBHOOK_TOKEN_CURRENT = "webhook_token_current"
CONF_WEBHOOK_TOKEN_PREV = "webhook_token_prev"
CONF_WEBHOOK_TOKEN_PREV_VALID_UNTIL = "webhook_token_prev_valid_until"
DEFAULT_TOKEN_GRACE_SECONDS = 120  # accept previous token for 2 minutes after rotation

# Token rotation cadence
ROTATE_INTERVAL = timedelta(days=1)       # daily rotation
RETRY_INTERVAL = timedelta(minutes=5)     # after-webhook retry cadence

# --- Automatic Reboot (Options) ---
CONF_AR_POWER_FAIL = "ar_power_fail"
CONF_AR_PING_FAIL = "ar_ping_fail"
CONF_AR_TRIGGER_MIN = "ar_trigger_minutes"
CONF_AR_DELAY_MIN = "ar_post_reboot_delay_minutes"
CONF_AR_ANY_FAIL = "ar_any_fail"
CONF_AR_MAX_REBOOTS = "ar_max_reboots"
CONF_AR_TARGET_1 = "ar_target_1"
CONF_AR_TARGET_2 = "ar_target_2"
CONF_AR_TARGET_3 = "ar_target_3"
CONF_AR_TARGET_4 = "ar_target_4"
CONF_AR_TARGET_5 = "ar_target_5"
CONF_AR_OFF_SECONDS = "ar_off_duration_seconds"

# Defaults
DEFAULT_AR_POWER_FAIL = True
DEFAULT_AR_PING_FAIL = True
DEFAULT_AR_TRIGGER_MIN = 2
DEFAULT_AR_DELAY_MIN = 1
DEFAULT_AR_ANY_FAIL = False
DEFAULT_AR_MAX_REBOOTS = 10
DEFAULT_AR_OFF_SECONDS = 30