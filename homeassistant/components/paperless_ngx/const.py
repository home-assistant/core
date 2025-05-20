"""Constants for the Paperless-ngx integration."""

import logging

from homeassistant.const import Platform

DOMAIN = "paperless_ngx"

PLATFORMS: list[Platform] = [Platform.UPDATE]

LOGGER = logging.getLogger(__package__)

PAPERLESS_CHANGELOGS = "https://docs.paperless-ngx.com/changelog/"
