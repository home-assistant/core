"""KNX Websocket API."""
from __future__ import annotations

from collections.abc import Callable
from typing import Final

from knx_frontend import get_build_id, locate_dir
import voluptuous as vol
from xknx.dpt import DPTArray
from xknx.telegram import Telegram, TelegramDirection
from xknx.telegram.apci import GroupValueRead, GroupValueResponse, GroupValueWrite

from homeassistant.components import panel_custom, websocket_api
from homeassistant.core import HomeAssistant, callback
import homeassistant.util.dt as dt_util

from .const import (
    DOMAIN,
    AsyncMessageCallbackType,
    KNXBusMonitorMessage,
    MessageCallbackType,
)

URL_BASE: Final = "/knx_static"


async def register_panel(hass: HomeAssistant) -> None:
    """Register the KNX Panel and Websocket API."""
    websocket_api.async_register_command(hass, ws_info)
    websocket_api.async_register_command(hass, ws_subscribe_telegram)

    if DOMAIN not in hass.data.get("frontend_panels", {}):
        path = locate_dir()
        build_id = get_build_id()
        hass.http.register_static_path(
            URL_BASE, path, cache_headers=(build_id != "dev")
        )
        await panel_custom.async_register_panel(
            hass=hass,
            frontend_url_path=DOMAIN,
            webcomponent_name="knx-frontend",
            sidebar_title=DOMAIN.upper(),
            sidebar_icon="mdi:bus-electric",
            module_url=f"{URL_BASE}/entrypoint-{build_id}.js",
            embed_iframe=True,
            require_admin=True,
        )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "knx/info",
    }
)
@callback
def ws_info(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Handle get info command."""
    xknx = hass.data[DOMAIN].xknx
    connection.send_result(
        msg["id"],
        {
            "version": xknx.version,
            "connected": xknx.connection_manager.connected.is_set(),
            "current_address": str(xknx.current_address),
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "knx/subscribe_telegrams",
    }
)
@callback
def ws_subscribe_telegram(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Subscribe to incoming and outgoing KNX telegrams."""

    async def forward_telegrams(telegram: Telegram) -> None:
        """Forward events to websocket."""
        payload: str
        if isinstance(telegram.payload, (GroupValueWrite, GroupValueResponse)):
            if isinstance(telegram.payload.value, DPTArray):
                payload = f"0x{bytes(telegram.payload.value.value).hex()}"
            else:
                payload = f"0b{telegram.payload.value.value:06b}"
        elif isinstance(telegram.payload, GroupValueRead):
            payload = ""
        else:
            return

        direction = (
            "group_monitor_incoming"
            if telegram.direction == TelegramDirection.INCOMING
            else "group_monitor_outgoing"
        )
        bus_message: KNXBusMonitorMessage = KNXBusMonitorMessage(
            destination_address=str(telegram.destination_address),
            payload=payload,
            type=str(telegram.payload.__class__.__name__),
            source_address=str(telegram.source_address),
            direction=direction,
            timestamp=dt_util.as_local(dt_util.utcnow()).strftime("%H:%M:%S.%f")[:-3],
        )

        connection.send_message(
            websocket_api.event_message(
                msg["id"],
                bus_message,
            )
        )

    connection.subscriptions[msg["id"]] = async_subscribe_telegrams(
        hass, forward_telegrams
    )

    connection.send_message(websocket_api.result_message(msg["id"]))


def async_subscribe_telegrams(
    hass: HomeAssistant,
    telegram_callback: AsyncMessageCallbackType | MessageCallbackType,
) -> Callable[[], None]:
    """Subscribe to telegram received callback."""
    xknx = hass.data[DOMAIN].xknx

    unregister = xknx.telegram_queue.register_telegram_received_cb(
        telegram_callback, match_for_outgoing=True
    )

    def async_remove() -> None:
        """Remove callback."""
        xknx.telegram_queue.unregister_telegram_received_cb(unregister)

    return async_remove
