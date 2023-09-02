"""Config flow for the Reolink camera component."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from reolink_aio.exceptions import ApiError, CredentialsInvalidError, ReolinkError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import format_mac

from . import ReolinkData
from .const import CONF_PROTOCOL, CONF_USE_HTTPS, DOMAIN
from .exceptions import ReolinkException, ReolinkWebhookException, UserNotAdmin
from .host import ReolinkHost


def has_connection_problem(hass: HomeAssistant, config_entry: config_entries.ConfigEntry) -> bool:
    """Check if a existing entry has a connection problem."""
    reolink_data: ReolinkData | None = hass.data.get(DOMAIN, {}).get(
        config_entry.entry_id
    )
    connection_problem = (
        reolink_data is not None
        and config_entry.state == config_entries.ConfigEntryState.LOADED
        and reolink_data.device_coordinator.last_update_success
    )
    return connection_problem