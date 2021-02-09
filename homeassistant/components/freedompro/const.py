"""Constants for the Freedompro integration."""
from datetime import timedelta

COORDINATOR = "coordinator"
DOMAIN = "freedompro"
FREEDOMPRO_CONFIG = "freedompro_config"
FREEDOMPRO_PARALLEL_UPDATES = 1
FREEDOMPRO_SCAN_INTERVAL = timedelta(minutes=5)
FREEDOMPRO_URL = "https://api.freedompro.eu/api/freedompro/accessories"
UNDO_UPDATE_LISTENER = "undo_update_listener"
