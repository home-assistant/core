"""Push-subscription webhook handlers."""
# pylint: disable=home-assistant-use-runtime-data  # Uses legacy hass.data[DOMAIN] pattern

from typing import Any

from aiohttp.web import Response
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from ..const import (
    PUSH_SUBSCRIPTION_ENTITY_IDS,
    PUSH_SUBSCRIPTION_ID,
    PUSH_SUBSCRIPTION_MAX_ENTITY_IDS,
    PUSH_SUBSCRIPTION_TARGET,
    PUSH_SUBSCRIPTION_TOKEN,
)
from ..helpers import empty_okay_response
from ..webhook import WEBHOOK_COMMANDS, validate_schema
from .store import remove_push_subscription, store_push_subscription


def _unique_entity_ids(entity_ids: list[str]) -> list[str]:
    """Remove duplicate entity_ids while preserving order.

    Duplicates would otherwise arm the same state-change listener more than once.
    """
    return list(dict.fromkeys(entity_ids))


@WEBHOOK_COMMANDS.register("register_push_subscription")
@validate_schema(
    {
        vol.Required(PUSH_SUBSCRIPTION_ID): cv.string,
        vol.Required(PUSH_SUBSCRIPTION_TOKEN): cv.string,
        vol.Required(PUSH_SUBSCRIPTION_ENTITY_IDS): vol.All(
            cv.ensure_list,
            [cv.entity_id],
            vol.Length(min=1, max=PUSH_SUBSCRIPTION_MAX_ENTITY_IDS),
            _unique_entity_ids,
        ),
        vol.Optional(PUSH_SUBSCRIPTION_TARGET): cv.string,
    }
)
async def webhook_register_push_subscription(
    hass: HomeAssistant, config_entry: ConfigEntry, data: dict[str, Any]
) -> Response:
    """Register/update a push subscription tied to entity state changes.

    Re-sending the same subscription_id with a new token or entity list updates
    the existing subscription in place (the common case when a push token
    rotates), so apps can call this idempotently.
    """
    store_push_subscription(
        hass,
        config_entry.data[CONF_WEBHOOK_ID],
        data[PUSH_SUBSCRIPTION_ID],
        data[PUSH_SUBSCRIPTION_TOKEN],
        data[PUSH_SUBSCRIPTION_ENTITY_IDS],
        data.get(PUSH_SUBSCRIPTION_TARGET),
    )
    return empty_okay_response()


@WEBHOOK_COMMANDS.register("remove_push_subscription")
@validate_schema(
    {
        vol.Required(PUSH_SUBSCRIPTION_ID): cv.string,
    }
)
async def webhook_remove_push_subscription(
    hass: HomeAssistant, config_entry: ConfigEntry, data: dict[str, str]
) -> Response:
    """Remove a push subscription (app no longer wants pushes for it)."""
    remove_push_subscription(
        hass, config_entry.data[CONF_WEBHOOK_ID], data[PUSH_SUBSCRIPTION_ID]
    )
    return empty_okay_response()
