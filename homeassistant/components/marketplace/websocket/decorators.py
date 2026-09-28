"""Decorators for the WebSocket commands of the Marketplace."""

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from ..base import MarketplaceConfigEntry, MarketplaceManager
from ..const import DOMAIN

ERR_GITHUB_NOT_CONNECTED = "github_not_connected"
ERR_GITHUB_RATE_LIMITED = "github_rate_limited"
ERR_NOT_LOADED = "not_loaded"
ERR_WARNING_NOT_ACCEPTED = "warning_not_accepted"
ERR_REPOSITORY_NOT_FOUND = "repository_not_found"


def send_translated_error(
    connection: websocket_api.ActiveConnection,
    msg_id: int,
    code: str,
    translation_key: str,
    translation_placeholders: dict[str, str] | None = None,
) -> None:
    """Answer with an error the panel shows as is, so it has to be translated."""
    # The exception renders the message in the language of Home Assistant
    message = str(
        HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders=translation_placeholders,
        )
    )
    connection.send_error(
        msg_id,
        code,
        message,
        translation_key=translation_key,
        translation_domain=DOMAIN,
        translation_placeholders=translation_placeholders,
    )


def send_repository_not_found(
    connection: websocket_api.ActiveConnection, msg_id: int, repository_id: str
) -> None:
    """Answer that the Marketplace does not know the repository."""
    send_translated_error(
        connection,
        msg_id,
        ERR_REPOSITORY_NOT_FOUND,
        "repository_not_found",
        {"repository": repository_id},
    )


type MarketplaceCommandHandler = Callable[
    [HomeAssistant, websocket_api.ActiveConnection, dict[str, Any], MarketplaceManager],
    Awaitable[None],
]
type CommandHandler = Callable[
    [HomeAssistant, websocket_api.ActiveConnection, dict[str, Any]],
    Awaitable[None],
]


def marketplace_command(
    *, requires_accepted_warning: bool = False, requires_github: bool = False
) -> Callable[[MarketplaceCommandHandler], CommandHandler]:
    """Hand the command the loaded Marketplace, or answer why there is none.

    The commands are registered once per start, the entry can be loaded later
    or not at all.
    """

    def decorator(handler: MarketplaceCommandHandler) -> CommandHandler:
        @wraps(handler)
        async def with_marketplace(
            hass: HomeAssistant,
            connection: websocket_api.ActiveConnection,
            msg: dict[str, Any],
        ) -> None:
            if not (entries := hass.config_entries.async_loaded_entries(DOMAIN)):
                send_translated_error(
                    connection, msg["id"], ERR_NOT_LOADED, "not_loaded"
                )
                return

            entry: MarketplaceConfigEntry = entries[0]
            marketplace = entry.runtime_data

            if requires_accepted_warning and not marketplace.warning_accepted(
                connection.user.id
            ):
                send_translated_error(
                    connection,
                    msg["id"],
                    ERR_WARNING_NOT_ACCEPTED,
                    "warning_not_accepted",
                )
                return

            if requires_github and not marketplace.github_connected:
                send_translated_error(
                    connection,
                    msg["id"],
                    ERR_GITHUB_NOT_CONNECTED,
                    "github_not_connected",
                )
                return

            await handler(hass, connection, msg, marketplace)

        return with_marketplace

    return decorator
