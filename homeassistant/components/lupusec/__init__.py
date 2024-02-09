"""Support for Lupusec Home Security system."""
from json import JSONDecodeError
import logging

import lupupy
from lupupy.exceptions import LupusecException
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

from .const import INTEGRATION_TITLE, ISSUE_PLACEHOLDER

_LOGGER = logging.getLogger(__name__)

DOMAIN = "lupusec"

NOTIFICATION_ID = "lupusec_notification"
NOTIFICATION_TITLE = "Lupusec Security Setup"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Required(CONF_IP_ADDRESS): cv.string,
                vol.Optional(CONF_NAME): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS: list[Platform] = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
]


async def handle_async_init_result(hass: HomeAssistant, domain: str, conf: dict):
    """Handle the result of the async_init to issue deprecated warnings."""
    flow = hass.config_entries.flow
    result = await flow.async_init(domain, context={"source": SOURCE_IMPORT}, data=conf)

    if (
        result["type"] == FlowResultType.CREATE_ENTRY
        or result["reason"] == "already_configured"
    ):
        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2024.8.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": INTEGRATION_TITLE,
            },
        )
    else:
        async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_${result['reason']}",
            breaks_in_ha_version="2024.8.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_${result['reason']}",
            translation_placeholders=ISSUE_PLACEHOLDER,
        )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the lupusec integration."""

    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    hass.async_create_task(handle_async_init_result(hass, DOMAIN, conf))

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration using UI."""

    host = entry.data[CONF_HOST]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    try:
        lupusec_system = await hass.async_add_executor_job(
            lupupy.Lupusec, username, password, host
        )
    except LupusecException:
        _LOGGER.error("Failed to connect to Lupusec device at %s", host)
        return False
    except JSONDecodeError:
        _LOGGER.error("Failed to connect to Lupusec device at %s", host)
        return False

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = lupusec_system

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True
