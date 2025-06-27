"""Support for sending data to Dweet.io."""

import voluptuous as vol

from homeassistant.const import CONF_NAME, CONF_WHITELIST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.typing import ConfigType

DOMAIN = "dweet"


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_NAME): cv.string,
                vol.Required(CONF_WHITELIST, default=[]): vol.All(
                    cv.ensure_list, [cv.entity_id]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Dweet.io component."""
    ir.create_issue(
        hass,
        DOMAIN,
        DOMAIN,
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="integration_removed",
    )

    return True
