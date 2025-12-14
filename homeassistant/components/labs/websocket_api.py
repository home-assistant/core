"""Websocket API for the Home Assistant Labs integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.backup import async_get_manager
from homeassistant.const import EVENT_LABS_UPDATED
from homeassistant.core import HomeAssistant, callback

from .const import LABS_DATA
from .helpers import async_is_preview_feature_enabled, async_listen
from .models import EventLabsUpdatedData


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the number websocket API."""
    websocket_api.async_register_command(hass, websocket_list_preview_features)
    websocket_api.async_register_command(hass, websocket_update_preview_feature)
    websocket_api.async_register_command(hass, websocket_subscribe_feature)


@callback
@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "labs/list"})
def websocket_list_preview_features(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """List all lab preview features filtered by loaded integrations."""
    labs_data = hass.data[LABS_DATA]
    loaded_components = hass.config.components

    preview_features: list[dict[str, Any]] = [
        preview_feature.to_dict(
            enabled=(preview_feature.domain, preview_feature.preview_feature)
            in labs_data.data.preview_feature_status
        )
        for preview_feature in labs_data.preview_features.values()
        if preview_feature.domain in loaded_components
    ]

    connection.send_result(msg["id"], {"features": preview_features})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "labs/update",
        vol.Required("domain"): str,
        vol.Required("preview_feature"): str,
        vol.Required("enabled"): bool,
        vol.Optional("create_backup", default=False): bool,
    }
)
@websocket_api.async_response
async def websocket_update_preview_feature(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Update a lab preview feature state."""
    domain = msg["domain"]
    preview_feature = msg["preview_feature"]
    enabled = msg["enabled"]
    create_backup = msg["create_backup"]

    labs_data = hass.data[LABS_DATA]

    preview_feature_id = f"{domain}.{preview_feature}"

    if preview_feature_id not in labs_data.preview_features:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_NOT_FOUND,
            f"Preview feature {preview_feature_id} not found",
        )
        return

    # Create backup if requested and enabled
    if create_backup and enabled:
        try:
            backup_manager = async_get_manager(hass)
            await backup_manager.async_create_automatic_backup()
        except Exception as err:  # noqa: BLE001 - websocket handlers can catch broad exceptions
            connection.send_error(
                msg["id"],
                websocket_api.ERR_UNKNOWN_ERROR,
                f"Error creating backup: {err}",
            )
            return

    if enabled:
        labs_data.data.preview_feature_status.add((domain, preview_feature))
    else:
        labs_data.data.preview_feature_status.discard((domain, preview_feature))

    await labs_data.store.async_save(labs_data.data.to_store_format())

    event_data: EventLabsUpdatedData = {
        "domain": domain,
        "preview_feature": preview_feature,
        "enabled": enabled,
    }
    hass.bus.async_fire(EVENT_LABS_UPDATED, event_data)

    connection.send_result(msg["id"])


@callback
@websocket_api.websocket_command(
    {
        vol.Required("type"): "labs/subscribe",
        vol.Required("domain"): str,
        vol.Required("preview_feature"): str,
    }
)
def websocket_subscribe_feature(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Subscribe to a specific lab preview feature updates."""
    domain = msg["domain"]
    preview_feature_key = msg["preview_feature"]
    labs_data = hass.data[LABS_DATA]

    preview_feature_id = f"{domain}.{preview_feature_key}"

    if preview_feature_id not in labs_data.preview_features:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_NOT_FOUND,
            f"Preview feature {preview_feature_id} not found",
        )
        return

    preview_feature = labs_data.preview_features[preview_feature_id]

    @callback
    def send_event() -> None:
        """Send feature state to client."""
        enabled = async_is_preview_feature_enabled(hass, domain, preview_feature_key)
        connection.send_message(
            websocket_api.event_message(
                msg["id"],
                preview_feature.to_dict(enabled=enabled),
            )
        )

    connection.subscriptions[msg["id"]] = async_listen(
        hass, domain, preview_feature_key, send_event
    )

    connection.send_result(msg["id"])
    send_event()
