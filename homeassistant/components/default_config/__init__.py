"""Component providing default configuration for new users."""

try:
    import av
except ImportError:
    av = None

import logging.handlers
from pathlib import Path

import voluptuous as vol

from homeassistant.const import CONF_EXCLUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import Integration
from homeassistant.setup import async_process_deps_reqs, async_setup_component

__LOGGER = logging.getLogger(__name__)

DOMAIN = "default_config"

INTEGRATIONS = [
    "automation",
    "cloud",
    "counter",
    "dhcp",
    "energy",
    "frontend",
    "history",
    "input_boolean",
    "input_button",
    "input_datetime",
    "input_number",
    "input_select",
    "input_text",
    "logbook",
    "map",
    "media_source",
    "mobile_app",
    "my",
    "network",
    "person",
    "scene",
    "script",
    "ssdp",
    "sun",
    "system_health",
    "tag",
    "timer",
    "usb",
    "updater",
    "webhook",
    "zeroconf",
    "zone",
]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_EXCLUDE, default=[]): vol.All(
                    cv.ensure_list, [vol.In(INTEGRATIONS)]
                ),
            },
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Initialize default configuration."""
    if av is None:
        return True

    if await __configure_integrations(hass, config) is False:
        return False

    return await async_setup_component(hass, "stream", config)


async def __configure_integrations(hass: HomeAssistant, config: ConfigType):
    excluded_integrations = __get_excluded_integrations(config)
    __LOGGER.info("Excluded integrations %s", excluded_integrations)

    parent_integration = Integration(
        hass,
        "",
        Path(""),
        {
            "domain": "default_config_dependencies",
            "dependencies": [
                integration
                for integration in INTEGRATIONS
                if integration not in excluded_integrations
            ],
        },
    )

    return await async_process_deps_reqs(hass, config, parent_integration)


def __get_excluded_integrations(config: ConfigType):
    conf = config.get(DOMAIN, {})
    return conf.get(CONF_EXCLUDE, [])
