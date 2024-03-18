"""Constants for the Webmin integration."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)
DOMAIN = "webmin"

DEFAULT_PORT = 10000
DEFAULT_SSL = True
DEFAULT_VERIFY_SSL = False
