"""Helpers for the Route53 integration."""

from dataclasses import dataclass
from http import HTTPStatus

import boto3
import requests

from .const import DOMAIN, LOGGER


@dataclass(frozen=True, slots=True)
class Route53Data:
    """Route53 configuration."""

    aws_access_key_id: str
    aws_secret_access_key: str
    zone: str
    domain: str
    records: list[str]
    ttl: int


def update_route53(data: Route53Data) -> None:
    """Update the Route53 records with the current public IP address."""
    _update_route53(
        data.aws_access_key_id,
        data.aws_secret_access_key,
        data.zone,
        data.domain,
        data.records,
        data.ttl,
    )


def _get_fqdn(record, domain):
    if record == ".":
        return domain
    return f"{record}.{domain}"


def _update_route53(
    aws_access_key_id: str,
    aws_secret_access_key: str,
    zone: str,
    domain: str,
    records: list[str],
    ttl: int,
):
    """Update the Route53 records with the current public IP address."""
    LOGGER.debug("Starting update for zone %s", zone)

    client = boto3.client(
        DOMAIN,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )

    # Get the IP Address and build an array of changes
    try:
        ipaddress = requests.get("https://api.ipify.org/", timeout=5).text

    except requests.RequestException:
        LOGGER.warning("Unable to reach the ipify service")
        return

    changes = []
    for record in records:
        LOGGER.debug("Processing record: %s", record)

        changes.append(
            {
                "Action": "UPSERT",
                "ResourceRecordSet": {
                    "Name": _get_fqdn(record, domain),
                    "Type": "A",
                    "TTL": ttl,
                    "ResourceRecords": [{"Value": ipaddress}],
                },
            }
        )

    LOGGER.debug("Submitting the following changes to Route53")
    LOGGER.debug(changes)

    response = client.change_resource_record_sets(
        HostedZoneId=zone, ChangeBatch={"Changes": changes}
    )
    LOGGER.debug("Response is %s", response)

    if response["ResponseMetadata"]["HTTPStatusCode"] != HTTPStatus.OK:
        LOGGER.warning(response)
