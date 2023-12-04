"""Support for Digital Ocean."""

from datetime import timedelta
import functools
import logging

import digitalocean
import voluptuous as vol

from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import Throttle

from .constants import MIN_TIME_BETWEEN_DOMAIN_UPDATES
from .exceptions import DomainRecordAlreadySet, DomainRecordsNotFound
from .schemas import UPDATE_DOMAIN_RECORD_SCHEMA
from .services import handle_update_domain_record

_LOGGER = logging.getLogger(__name__)

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

DATA_DIGITAL_OCEAN = "data_do"
DIGITAL_OCEAN_PLATFORMS = [Platform.SWITCH, Platform.BINARY_SENSOR]
DOMAIN = "digital_ocean"

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_ACCESS_TOKEN): cv.string})},
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Digital Ocean component."""

    conf = config[DOMAIN]
    access_token = conf[CONF_ACCESS_TOKEN]

    digital = DigitalOcean(access_token)

    try:
        if not digital.manager.get_account():
            _LOGGER.error("No account found for the given API token")
            return False
    except digitalocean.baseapi.DataReadError:
        _LOGGER.error("API token not valid for authentication")
        return False

    hass.data[DATA_DIGITAL_OCEAN] = digital
    hass.services.register(
        DOMAIN,
        "update_domain_record",
        functools.partial(handle_update_domain_record, hass=hass),
        schema=UPDATE_DOMAIN_RECORD_SCHEMA,
    )
    return True


class DigitalOcean:
    """Handle all communication with the Digital Ocean API."""

    def __init__(self, access_token):
        """Initialize the Digital Ocean connection."""

        self._access_token = access_token
        self.data = None
        self.manager = digitalocean.Manager(token=self._access_token)

    def get_droplet_id(self, droplet_name):
        """Get the status of a Digital Ocean droplet."""
        droplet_id = None

        all_droplets = self.manager.get_all_droplets()
        for droplet in all_droplets:
            if droplet_name == droplet.name:
                droplet_id = droplet.id

        return droplet_id

    @Throttle(MIN_TIME_BETWEEN_DOMAIN_UPDATES)
    def update_domain_record(
        self, domain_name, record_name, record_value, record_type="A"
    ):
        """Update the appointed DNS record with the desired value."""
        domain = digitalocean.Domain(token=self._access_token, name=domain_name)
        try:
            records = domain.get_records()
        except digitalocean.baseapi.NotFoundError as exc:  # pragma: no cover
            raise DomainRecordsNotFound(
                f"Could not find records in domain {domain_name}"
            ) from exc

        for record in records:
            if record.name == record_name and record.type == record_type:
                if record.data == record_value:
                    raise DomainRecordAlreadySet(
                        f"Skipping update record {record_name} ({record_type}) "
                        f"of domain {domain_name}: value already set",
                    )
                record.data = record_value
                record.save()
                return True
        raise DomainRecordsNotFound(
            f"Cold not find record {record_name} ({record_type}) "
            f"in domain {domain_name}"
        )

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Use the data from Digital Ocean API."""
        self.data = self.manager.get_all_droplets()
