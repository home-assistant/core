"""Constants for the Route53 integration."""

import logging
from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .helpers import Route53Data

DOMAIN = "route53"

LOGGER = logging.getLogger(__package__)

DATA_ROUTE53: HassKey[Route53Data] = HassKey(DOMAIN)
