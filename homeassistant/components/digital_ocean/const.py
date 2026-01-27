"""Support for Digital Ocean."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from . import DigitalOcean

ATTR_CREATED_AT = "created_at"
ATTR_DROPLET_ID = "droplet_id"
ATTR_DROPLET_NAME = "droplet_name"
ATTR_FEATURES = "features"
ATTR_IPV4_ADDRESS = "ipv4_address"
ATTR_IPV6_ADDRESS = "ipv6_address"
ATTR_MEMORY = "memory"
ATTR_REGION = "region"
ATTR_VCPUS = "vcpus"

ATTRIBUTION = "Data provided by Digital Ocean"

CONF_DROPLETS = "droplets"

DOMAIN = "digital_ocean"
DATA_DIGITAL_OCEAN: HassKey[DigitalOcean] = HassKey(DOMAIN)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)
