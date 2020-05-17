"""Constants used for arcam."""
DOMAIN = "arcam_fmj"

SIGNAL_CLIENT_STARTED = "arcam.client_started"
SIGNAL_CLIENT_STOPPED = "arcam.client_stopped"
SIGNAL_CLIENT_DATA = "arcam.client_data"

EVENT_TURN_ON = "arcam_fmj.turn_on"

DEFAULT_PORT = 50000
DEFAULT_NAME = "Arcam FMJ"
DEFAULT_SCAN_INTERVAL = 5

DOMAIN_DATA_ENTRIES = f"{DOMAIN}.entries"
DOMAIN_DATA_TASKS = f"{DOMAIN}.tasks"
DOMAIN_DATA_CONFIG = f"{DOMAIN}.config"
