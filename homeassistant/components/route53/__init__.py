"""Update the IP addresses of your Route53 DNS records."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

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
from .helpers import async_update_records

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
                await async_update_records(hass, entry.data)
            except HomeAssistantError as err:
                errors.append(f"{entry.data[CONF_DOMAIN]}: {err}")
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

    async def update_records_interval(now: datetime) -> None:
        """Set up recurring update."""
        try:
            await async_update_records(hass, entry.data)
        except HomeAssistantError as err:
            _LOGGER.warning(err)

    try:
        await async_update_records(hass, entry.data)
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
