"""The Unify Circuit component."""

import voluptuous as vol

from homeassistant.const import CONF_NAME, CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery
import homeassistant.helpers.issue_registry as ir
from homeassistant.helpers.typing import ConfigType

DOMAIN = "circuit"
CONF_WEBHOOK = "webhook"

WEBHOOK_SCHEMA = vol.Schema(
    {vol.Optional(CONF_NAME): cv.string, vol.Required(CONF_URL): cv.string}
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {vol.Required(CONF_WEBHOOK): vol.All(cv.ensure_list, [WEBHOOK_SCHEMA])}
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Unify Circuit component."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        "service_removal",
        breaks_in_ha_version="2024.7.0",
        is_fixable=False,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="service_removal",
        translation_placeholders={"integration": "Unify Circuit", "domain": DOMAIN},
    )
    webhooks = config[DOMAIN][CONF_WEBHOOK]

    for webhook_conf in webhooks:
        hass.async_create_task(
            discovery.async_load_platform(
                hass, Platform.NOTIFY, DOMAIN, webhook_conf, config
            )
        )

    return True
