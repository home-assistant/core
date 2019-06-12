"""Update the IP addresses of your Route53 DNS records."""
from datetime import timedelta
import logging
from typing import List

import voluptuous as vol

from homeassistant.const import CONF_DOMAIN, CONF_TTL, CONF_ZONE
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import track_time_interval

_LOGGER = logging.getLogger(__name__)

CONF_ACCESS_KEY_ID = 'aws_access_key_id'
CONF_SECRET_ACCESS_KEY = 'aws_secret_access_key'
CONF_RECORDS = 'records'

DOMAIN = 'route53'

INTERVAL = timedelta(minutes=60)
DEFAULT_TTL = 300

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_ACCESS_KEY_ID): cv.string,
        vol.Required(CONF_DOMAIN): cv.string,
        vol.Required(CONF_RECORDS): vol.All(cv.ensure_list, [cv.string]),
        vol.Required(CONF_SECRET_ACCESS_KEY): cv.string,
        vol.Required(CONF_ZONE): cv.string,
        vol.Optional(CONF_TTL, default=DEFAULT_TTL): cv.positive_int,
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Route53 component."""
    domain = config[DOMAIN][CONF_DOMAIN]
    records = config[DOMAIN][CONF_RECORDS]
    zone = config[DOMAIN][CONF_ZONE]
    aws_access_key_id = config[DOMAIN][CONF_ACCESS_KEY_ID]
    aws_secret_access_key = config[DOMAIN][CONF_SECRET_ACCESS_KEY]
    ttl = config[DOMAIN][CONF_TTL]

    def update_records_interval(now):
        """Set up recurring update."""
        _update_route53(
            aws_access_key_id,
            aws_secret_access_key,
            zone,
            domain,
            records,
            ttl
        )

    def update_records_service(now):
        """Set up service for manual trigger."""
        _update_route53(
            aws_access_key_id,
            aws_secret_access_key,
            zone,
            domain,
            records,
            ttl
        )

    track_time_interval(hass, update_records_interval, INTERVAL)

    hass.services.register(DOMAIN, 'update_records', update_records_service)
    return True


def _update_route53(
        aws_access_key_id: str,
        aws_secret_access_key: str,
        zone: str,
        domain: str,
        records: List[str],
        ttl: int,
):
    import boto3
    from ipify import get_ip
    from ipify import exceptions

    _LOGGER.debug("Starting update for zone %s", zone)

    client = boto3.client(
        DOMAIN,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )

    # Get the IP Address and build an array of changes
    try:
        ipaddress = get_ip()

    except exceptions.ConnectionError:
        _LOGGER.warning("Unable to reach the ipify service")
        return

    except exceptions.ServiceError:
        _LOGGER.warning("Unable to complete the ipfy request")
        return

    changes = []
    for record in records:
        _LOGGER.debug("Processing record: %s", record)

        changes.append({
            'Action': 'UPSERT',
            'ResourceRecordSet': {
                'Name': '{}.{}'.format(record, domain),
                'Type': 'A',
                'TTL': ttl,
                'ResourceRecords': [
                    {'Value': ipaddress},
                ],
            }
        })

    _LOGGER.debug("Submitting the following changes to Route53")
    _LOGGER.debug(changes)

    response = client.change_resource_record_sets(
        HostedZoneId=zone, ChangeBatch={'Changes': changes})
    _LOGGER.debug("Response is %s", response)

    if response['ResponseMetadata']['HTTPStatusCode'] != 200:
        _LOGGER.warning(response)
