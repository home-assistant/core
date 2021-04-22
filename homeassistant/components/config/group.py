"""Provide configuration end points for Groups."""
from homeassistant.components.group import (
    DOMAIN,
    GROUP_SCHEMA,
    GroupIntegrationRegistry,
)
from homeassistant.config import GROUP_CONFIG_PATH
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv

from . import EditKeyBasedConfigView


async def async_setup(hass):
    """Set up the Group config API."""

    async def hook(action, config_key):
        """post_write_hook for Config View that reloads groups."""
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD)

    hass.http.register_view(
        EditKeyBasedConfigView(
            "group",
            "config",
            GROUP_CONFIG_PATH,
            cv.slug,
            GROUP_SCHEMA,
            post_write_hook=hook,
        )
    )
    return True


@callback
def async_describe_on_off_states(
    hass: HomeAssistant, registry: GroupIntegrationRegistry
) -> None:
    """Describe group on off states."""
    return
