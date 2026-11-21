"""Common code for TCP component."""

from typing import Any, Final

import probatio

from homeassistant.components.homeassistant import DOMAIN as HOMEASSISTANT_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PAYLOAD,
    CONF_PORT,
    CONF_SSL,
    CONF_TIMEOUT,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_BUFFER_SIZE,
    CONF_TITLE,
    CONF_VALUE_ON,
    DEFAULT_BUFFER_SIZE,
    DEFAULT_NAME,
    DEFAULT_SSL,
    DEFAULT_TIMEOUT,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)

TCP_PLATFORM_SCHEMA: Final[dict[probatio.Marker, Any]] = {
    probatio.Required(CONF_HOST): cv.string,
    probatio.Required(CONF_PORT): probatio.Port(),
    probatio.Required(CONF_PAYLOAD): cv.string,
    probatio.Optional(CONF_BUFFER_SIZE, default=DEFAULT_BUFFER_SIZE): cv.positive_int,
    probatio.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    probatio.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    probatio.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    probatio.Optional(CONF_VALUE_ON): cv.string,
    probatio.Optional(CONF_VALUE_TEMPLATE): cv.template,
    probatio.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
    probatio.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
}

YAML_KEYS: Final = {str(key) for key in TCP_PLATFORM_SCHEMA}


async def async_import_yaml(hass: HomeAssistant, config: ConfigType) -> None:
    """Import a YAML platform config and raise the deprecation issue."""
    data = {key: value for key, value in config.items() if key in YAML_KEYS}
    data[CONF_TITLE] = data.pop(CONF_NAME, DEFAULT_NAME)
    if (template := data.get(CONF_VALUE_TEMPLATE)) is not None:
        data[CONF_VALUE_TEMPLATE] = template.template

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=data
    )
    if (
        result["type"] is FlowResultType.ABORT
        and result["reason"] != "already_configured"
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{result['reason']}",
            breaks_in_ha_version="2027.6.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{result['reason']}",
        )
        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2027.6.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={"domain": DOMAIN, "integration_title": "TCP"},
    )
