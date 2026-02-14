"""Constants for the Abode Security System component."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from . import AbodeSystem

LOGGER = logging.getLogger(__package__)

DOMAIN = "abode"
DOMAIN_DATA: HassKey[AbodeSystem] = HassKey(DOMAIN)
ATTRIBUTION = "Data provided by goabode.com"

CONF_POLLING = "polling"
