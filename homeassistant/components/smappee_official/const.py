"""Define constants for the Smappee Official component."""

from datetime import timedelta

DEFAULT_NAME = "Smappee Official"

DOMAIN = "smappee_official"
DATA_CLIENT = "smappee_data"

SMAPPEE_COMPONENTS = ["sensor"]

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)
