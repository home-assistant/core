"""Constants for the Ubiquiti airOS integration."""

from datetime import timedelta

DOMAIN = "airos"

SCAN_INTERVAL = timedelta(minutes=1)

AIROS_HOST_KEY = "host"
AIROS_HOSTNAME_KEY = "hostname"
AIROS_DEVICE_ID_KEY = "device_id"
AIROS_DEVMODEL_KEY = "devmodel"
AIROS_FWVERSION_KEY = "fwversion"

MANUFACTURER = "Ubiquiti"

AIROS_DEFAULT_HOSTNAME = "Ubiquiti airOS Device"
