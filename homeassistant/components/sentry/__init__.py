"""The sentry integration."""
import logging
from typing import Any, Optional

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import __version__
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_DSN,
    CONF_ENVIRONMENT,
    CONF_TRACING,
    CONF_TRACING_SAMPLE_RATE,
    DOMAIN,
)


def _get_integrations() -> list:
    """Detect available Sentry integrations.

    Return a list of enabled integrations based on modules available.
    """
    integrations = []

    try:
        import sqlalchemy  # NOQA
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    except ImportError:
        pass
    else:
        integrations.append(SqlalchemyIntegration())

    try:
        import aiohttp  # NOQA
        from sentry_sdk.integrations.aiohttp import AioHttpIntegration
    except ImportError:
        pass
    else:
        integrations.append(AioHttpIntegration())

    return integrations


def sample_rate(value: Optional[Any]) -> float:
    """Validate sample_rate float between 0.0 and 1.0.

    None coerced to 1.0
    """
    if value is None:
        return 1.0
    try:
        float_value = float(value)
        if float_value < 0.0 or float_value > 1.0:
            raise vol.Invalid(
                "Invalid sample_rate value. float >= 0.0 and <= 1.0 required."
            )
        return float_value
    except Exception as err:
        raise vol.Invalid(f"Invalid sample_rate value: {err}")


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_DSN): cv.string,
                CONF_ENVIRONMENT: cv.string,
                CONF_TRACING: cv.boolean,
                CONF_TRACING_SAMPLE_RATE: sample_rate,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


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

    with_tracing = conf.get(CONF_TRACING)

    sentry_sdk.init(
        dsn=conf.get(CONF_DSN),
        environment=conf.get(CONF_ENVIRONMENT),
        integrations=[
            # https://docs.sentry.io/platforms/python/logging/
            LoggingIntegration(
                level=logging.INFO,  # Capture info and above as breadcrumbs
                event_level=logging.ERROR,  # Send errors as events
            ),
            *_get_integrations(),
        ],
        traces_sample_rate=(
            conf.get(CONF_TRACING_SAMPLE_RATE, 1.0) or 0.0 if with_tracing else 0.0
        ),
        traceparent_v2=with_tracing,
        release=f"homeassistant-{__version__}",
    )

    return True
