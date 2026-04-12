"""Constants for the guntamatic integration."""

from datetime import timedelta

DOMAIN = "guntamatic_sensor"
SCAN_INTERVAL = timedelta(seconds=30)
DIAGNOSTIC_SENSORS = {"Serial", "Version", "Operat. time", "Service Hrs"}
