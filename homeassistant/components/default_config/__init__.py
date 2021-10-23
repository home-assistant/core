"""Component providing default configuration for new users."""
try:
    import av
except ImportError:
    av = None

import asyncio

import voluptuous as vol

from homeassistant.const import CONF_EXCLUDE
import homeassistant.helpers.config_validation as cv
from homeassistant.setup import async_setup_component

DOMAIN = "default_config"

INTEGRATION_LIST = [
    "automation",
    "cloud",
    "counter",
    "dhcp",
    "energy",
    "frontend",
    "history",
    "input_boolean",
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
                    cv.ensure_list, [vol.In(INTEGRATION_LIST)]
                ),
            },
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Initialize default configuration."""
    conf = config.get(DOMAIN, {})
    exclude = conf.get(CONF_EXCLUDE, [])
    integration_list = INTEGRATION_LIST.copy()

    if av is not None:
        integration_list.append("stream")

    setup_tasks = [
        hass.async_add_job(async_setup_component, hass, integration, config)
        for integration in integration_list
        if integration not in exclude and integration not in hass.config.components
    ]

    done, _ = await asyncio.wait(setup_tasks)
    return all(done)
