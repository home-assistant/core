"""Const for the HEOS integration."""
from datetime import timedelta

COMMAND_RETRY_ATTEMPTS = 2
COMMAND_RETRY_DELAY = 1
DATA_CONTROLLER = "controller"
DATA_SOURCE_MANAGER = "source_manager"
DATA_DISCOVERED_HOSTS = "heos_discovered_hosts"
DATA_REGISTRY = "registry"
DOMAIN = 'heos'
SIGNAL_HEOS_SOURCES_UPDATED = "heos_sources_updated"
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1
MIN_UPDATE_SOURCES = timedelta(seconds=1)
SAVE_DELAY = 10
