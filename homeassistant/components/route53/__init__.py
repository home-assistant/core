"""Update the IP addresses of your Route53 DNS records."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
import logging
from typing import Any

import aiohttp
import boto3
import botocore.exceptions
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_DOMAIN, CONF_TTL, CONF_ZONE
from homeassistant.core import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    HomeAssistant,
    ServiceCall,
)
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ACCESS_KEY_ID,
    CONF_RECORDS,
    CONF_SECRET_ACCESS_KEY,
    DEFAULT_TTL,
    DOMAIN,
    INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class Route53Data:
    """Data for Route53 integration."""

    remove_interval: Callable[[], None]


type Route53ConfigEntry = ConfigEntry[Route53Data]


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_ACCESS_KEY_ID): cv.string,
                vol.Required(CONF_DOMAIN): cv.string,
                vol.Required(CONF_RECORDS): vol.All(cv.ensure_list, [cv.string]),
                vol.Required(CONF_SECRET_ACCESS_KEY): cv.string,
                vol.Required(CONF_ZONE): cv.string,
                vol.Optional(CONF_TTL, default=DEFAULT_TTL): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def _async_import_yaml(hass: HomeAssistant, conf: dict[str, Any]) -> None:
    """Import YAML config and create deprecation issues."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=conf,
    )
    if result.get("type") is FlowResultType.ABORT and result.get("reason") not in (
        "already_configured",
        "single_instance_allowed",
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{result.get('reason')}",
            breaks_in_ha_version="2027.3.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{result.get('reason')}",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "AWS Route53",
                "url": f"/config/integrations/dashboard/add?domain={DOMAIN}",
            },
        )
        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2027.3.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "AWS Route53",
        },
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Route53 component."""

    async def update_records_service(call: ServiceCall) -> None:
        """Set up service for manual trigger."""
        errors = []
        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            try:
                await _async_update_route53(
                    hass,
                    entry.data[CONF_ACCESS_KEY_ID],
                    entry.data[CONF_SECRET_ACCESS_KEY],
                    entry.data[CONF_ZONE],
                    entry.data[CONF_DOMAIN],
                    entry.data[CONF_RECORDS],
                    entry.data[CONF_TTL],
                )
            except HomeAssistantError as err:
                errors.append(str(err))
        if errors:
            raise HomeAssistantError(
                f"Error(s) updating Route53 records: {', '.join(errors)}"
            )

    hass.services.async_register(DOMAIN, "update_records", update_records_service)

    if DOMAIN in config:
        hass.async_create_task(_async_import_yaml(hass, config[DOMAIN]))

    return True


async def async_setup_entry(hass: HomeAssistant, entry: Route53ConfigEntry) -> bool:
    """Set up Route53 from a config entry."""
    domain = entry.data[CONF_DOMAIN]
    records = entry.data[CONF_RECORDS]
    zone = entry.data[CONF_ZONE]
    aws_access_key_id = entry.data[CONF_ACCESS_KEY_ID]
    aws_secret_access_key = entry.data[CONF_SECRET_ACCESS_KEY]
    ttl = entry.data[CONF_TTL]

    async def update_records_interval(now: datetime) -> None:
        """Set up recurring update."""
        try:
            await _async_update_route53(
                hass,
                aws_access_key_id,
                aws_secret_access_key,
                zone,
                domain,
                records,
                ttl,
            )
        except HomeAssistantError as err:
            _LOGGER.warning(err)

    try:
        await _async_update_route53(
            hass, aws_access_key_id, aws_secret_access_key, zone, domain, records, ttl
        )
    except HomeAssistantError as err:
        raise ConfigEntryNotReady from err

    remove_interval = async_track_time_interval(hass, update_records_interval, INTERVAL)

    entry.runtime_data = Route53Data(
        remove_interval=remove_interval,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: Route53ConfigEntry) -> bool:
    """Unload a config entry."""
    entry.runtime_data.remove_interval()
    return True


def _get_fqdn(record: str, domain: str) -> str:
    if record == ".":
        return domain
    return f"{record}.{domain}"


def _update_route53_records(
    aws_access_key_id: str,
    aws_secret_access_key: str,
    zone: str,
    changes: list[dict[str, Any]],
) -> None:
    client = boto3.client(
        "route53",
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )
    _LOGGER.debug("Submitting the following changes to Route53")
    _LOGGER.debug(changes)

    try:
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


async def _async_update_route53(
    hass: HomeAssistant,
    aws_access_key_id: str,
    aws_secret_access_key: str,
    zone: str,
    domain: str,
    records: list[str],
    ttl: int,
) -> None:
    _LOGGER.debug("Starting update for zone %s", zone)

    session = async_get_clientsession(hass)
    try:
        async with session.get(
            "https://api.ipify.org/", timeout=aiohttp.ClientTimeout(total=5)
        ) as resp:
            resp.raise_for_status()
            ipaddress = await resp.text()

    except (aiohttp.ClientError, TimeoutError) as err:
        raise HomeAssistantError("Unable to reach the ipify service") from err

    changes = []
    for record in records:
        _LOGGER.debug("Processing record: %s", record)

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

    await hass.async_add_executor_job(
        _update_route53_records, aws_access_key_id, aws_secret_access_key, zone, changes
    )
