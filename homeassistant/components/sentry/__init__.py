"""The sentry integration."""
import logging
import re

import sentry_sdk
from sentry_sdk.integrations.aiohttp import AioHttpIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import __version__ as current_version
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.loader import async_get_custom_components

from .const import CONF_DSN, CONF_ENVIRONMENT, DOMAIN, ENTITY_COMPONENTS

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {vol.Required(CONF_DSN): cv.string, CONF_ENVIRONMENT: cv.string}
        )
    },
    extra=vol.ALLOW_EXTRA,
)


LOGGER_INFO_REGEX = re.compile(r"^(\w+)\.?(\w+)?\.?(\w+)?\.?(\w+)?(?:\..*)?$")


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Sentry component."""
    conf = config.get(DOMAIN)
    if conf is not None:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Sentry from a config entry."""
    conf = entry.data

    hass.data[DOMAIN] = conf

    # https://docs.sentry.io/platforms/python/logging/
    sentry_logging = LoggingIntegration(
        level=logging.WARNING,  # Capture warning and above as breadcrumbs
        event_level=logging.ERROR,  # Send errors as events
    )

    # Find channel based on version number
    channel = "stable"
    if "dev0" in current_version:
        channel = "dev"
    elif "dev" in current_version:
        channel = "nightly"
    elif "b" in current_version:
        channel = "beta"

    # Additional/extra data collection
    huuid = await hass.helpers.instance_id.async_get()
    system_info = await hass.helpers.system_info.async_get_system_info()
    custom_components = await async_get_custom_components(hass)

    def before_send(event, hint):
        # Filter out handled events by default
        if "tags" in event and event.tags.get("handled", "no") == "yes":
            return None

        # Additional tags to add to the event
        additional_tags = {
            "channel": channel,
            "installation_type": system_info["installation_type"],
            "uuid": huuid,
        }

        # Find out all integrations in use, filter "auth", because it
        # triggers security rules, hiding all data.
        integrations = [
            integration
            for integration in hass.config.components
            if integration != "auth" and "." not in integration
        ]

        # Additional extra data to add to the event
        extra_data = {
            **system_info,
            "custom_components": "\n".join(sorted(custom_components)),
            "integrations": "\n".join(sorted(integrations)),
        }

        # Add additional tags based on what caused the event.
        platform = entity_platform.current_platform.get()
        if platform is not None:
            # This event happened in a platform
            additional_tags["custom_component"] = "no"
            additional_tags["integration"] = platform.platform_name
            additional_tags["platform"] = platform.domain
        elif "logger" in event:
            # Logger event, try to get integration information from the logger name.
            matches = LOGGER_INFO_REGEX.findall(event["logger"])
            if matches:
                group1, group2, group3, group4 = matches[0]
                # Handle the "homeassistant." package differently
                if group1 == "homeassistant" and group2 and group3:
                    if group2 == "components":
                        # This logger is from a component
                        additional_tags["custom_component"] = "no"
                        additional_tags["integration"] = group3
                        if group4 and group4 in ENTITY_COMPONENTS:
                            additional_tags["platform"] = group4
                    else:
                        # Not a component, could be helper, or something else.
                        additional_tags[group2] = group3
                else:
                    # Not the "homeassistant" package, this third-party
                    additional_tags["package"] = group1

        # If this event is caused by an integration, add a tag if this
        # integration is custom or not.
        if (
            "integration" in additional_tags
            and additional_tags["integration"] in custom_components
        ):
            additional_tags["custom_component"] = "yes"

        # Update event with all additional data
        event.setdefault("tags", {}).update(additional_tags)
        event.setdefault("extra", {}).update(extra_data)

        return event

    sentry_sdk.init(
        dsn=conf.get(CONF_DSN),
        environment=conf.get(CONF_ENVIRONMENT),
        integrations=[sentry_logging, AioHttpIntegration(), SqlalchemyIntegration()],
        release=current_version,
        before_send=before_send,
    )

    return True
