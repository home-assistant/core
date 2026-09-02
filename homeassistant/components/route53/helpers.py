"""Publish the current public IP address to Route53."""

from collections.abc import Mapping
from http import HTTPStatus
import logging
from typing import Any

import aiohttp
import boto3
import botocore.exceptions

from homeassistant.const import CONF_DOMAIN, CONF_TTL, CONF_ZONE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_ACCESS_KEY_ID, CONF_RECORDS, CONF_SECRET_ACCESS_KEY

_LOGGER = logging.getLogger(__name__)

IPIFY_URL = "https://api.ipify.org/"


def get_fqdn(record: str, domain: str) -> str:
    """Return the fully qualified name for a record."""
    if record == ".":
        return domain
    return f"{record}.{domain}"


# boto3 blocks twice here: creating the client reads its service model from
# disk, and the API call goes over the network. Both need the executor.
def update_route53_records(
    aws_access_key_id: str,
    aws_secret_access_key: str,
    zone: str,
    changes: list[dict[str, Any]],
) -> None:
    """Submit a change batch to Route53."""
    _LOGGER.debug("Submitting the following changes to Route53")
    _LOGGER.debug(changes)

    # Creating the client can raise too, for example on a malformed AWS config
    try:
        client = boto3.client(
            "route53",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )
        response = client.change_resource_record_sets(
            HostedZoneId=zone, ChangeBatch={"Changes": changes}
        )
    except (
        botocore.exceptions.BotoCoreError,
        botocore.exceptions.ClientError,
    ) as err:
        raise HomeAssistantError(f"Error updating Route53 records: {err}") from err
    _LOGGER.debug("Response is %s", response)

    if response["ResponseMetadata"]["HTTPStatusCode"] != HTTPStatus.OK:
        raise HomeAssistantError(f"Error updating Route53 records: {response}")


async def async_update_records(hass: HomeAssistant, data: Mapping[str, Any]) -> None:
    """Point the configured records at the current public IP address."""
    zone = data[CONF_ZONE]
    _LOGGER.debug("Starting update for zone %s", zone)

    session = async_get_clientsession(hass)
    try:
        async with session.get(
            IPIFY_URL, timeout=aiohttp.ClientTimeout(total=5)
        ) as resp:
            resp.raise_for_status()
            ipaddress = await resp.text()
    except (aiohttp.ClientError, TimeoutError) as err:
        raise HomeAssistantError("Unable to reach the ipify service") from err

    changes = [
        {
            "Action": "UPSERT",
            "ResourceRecordSet": {
                "Name": get_fqdn(record, data[CONF_DOMAIN]),
                "Type": "A",
                "TTL": data[CONF_TTL],
                "ResourceRecords": [{"Value": ipaddress}],
            },
        }
        for record in data[CONF_RECORDS]
    ]

    await hass.async_add_executor_job(
        update_route53_records,
        data[CONF_ACCESS_KEY_ID],
        data[CONF_SECRET_ACCESS_KEY],
        zone,
        changes,
    )
