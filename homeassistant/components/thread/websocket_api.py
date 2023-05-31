"""The thread websocket API."""
from __future__ import annotations

from typing import Any

from python_otbr_api.tlv_parser import TLVError
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from . import dataset_store, discovery


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the sensor websocket API."""
    websocket_api.async_register_command(hass, ws_add_dataset)
    websocket_api.async_register_command(hass, ws_delete_dataset)
    websocket_api.async_register_command(hass, ws_discover_routers)
    websocket_api.async_register_command(hass, ws_get_dataset)
    websocket_api.async_register_command(hass, ws_list_datasets)
    websocket_api.async_register_command(hass, ws_set_preferred_dataset)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "thread/add_dataset_tlv",
        vol.Required("source"): str,
        vol.Required("tlv"): str,
    }
)
@websocket_api.async_response
async def ws_add_dataset(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Add a thread dataset."""
    source = msg["source"]
    tlv = msg["tlv"]

    try:
        await dataset_store.async_add_dataset(hass, source, tlv)
    except TLVError as exc:
        connection.send_error(
            msg["id"], websocket_api.const.ERR_INVALID_FORMAT, str(exc)
        )
        return

    connection.send_result(msg["id"])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "thread/set_preferred_dataset",
        vol.Required("dataset_id"): str,
    }
)
@websocket_api.async_response
async def ws_set_preferred_dataset(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Add a thread dataset."""
    dataset_id = msg["dataset_id"]

    store = await dataset_store.async_get_store(hass)
    try:
        store.preferred_dataset = dataset_id
    except KeyError:
        connection.send_error(
            msg["id"], websocket_api.const.ERR_NOT_FOUND, "unknown dataset"
        )
        return

    connection.send_result(msg["id"])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "thread/delete_dataset",
        vol.Required("dataset_id"): str,
    }
)
@websocket_api.async_response
async def ws_delete_dataset(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Delete a thread dataset."""
    dataset_id = msg["dataset_id"]

    store = await dataset_store.async_get_store(hass)
    try:
        store.async_delete(dataset_id)
    except KeyError as exc:
        connection.send_error(msg["id"], websocket_api.const.ERR_NOT_FOUND, str(exc))
        return
    except dataset_store.DatasetPreferredError as exc:
        connection.send_error(msg["id"], websocket_api.const.ERR_NOT_ALLOWED, str(exc))
        return

    connection.send_result(msg["id"])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "thread/get_dataset_tlv",
        vol.Required("dataset_id"): str,
    }
)
@websocket_api.async_response
async def ws_get_dataset(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Get a thread dataset in TLV format."""
    dataset_id = msg["dataset_id"]

    store = await dataset_store.async_get_store(hass)
    if not (dataset := store.async_get(dataset_id)):
        connection.send_error(
            msg["id"], websocket_api.const.ERR_NOT_FOUND, "unknown dataset"
        )
        return

    connection.send_result(msg["id"], {"tlv": dataset.tlv})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "thread/list_datasets",
    }
)
@websocket_api.async_response
async def ws_list_datasets(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Get a list of thread datasets."""

    store = await dataset_store.async_get_store(hass)
    result = []
    preferred_dataset = store.preferred_dataset
    for dataset in store.datasets.values():
        result.append(
            {
                "channel": dataset.channel,
                "created": dataset.created,
                "dataset_id": dataset.id,
                "extended_pan_id": dataset.extended_pan_id,
                "network_name": dataset.network_name,
                "pan_id": dataset.pan_id,
                "preferred": dataset.id == preferred_dataset,
                "source": dataset.source,
            }
        )

    connection.send_result(msg["id"], {"datasets": result})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "thread/discover_routers",
    }
)
@websocket_api.async_response
async def ws_discover_routers(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Discover Thread routers."""

    @callback
    def router_discovered(key: str, data: discovery.ThreadRouterDiscoveryData) -> None:
        """Forward router discovery or update to websocket."""

        connection.send_message(
            websocket_api.event_message(
                msg["id"],
                {
                    "type": "router_discovered",
                    "key": key,
                    "data": data,
                },
            )
        )

    @callback
    def router_removed(key: str) -> None:
        """Forward router removed to websocket."""

        connection.send_message(
            websocket_api.event_message(
                msg["id"],
                {
                    "type": "router_removed",
                    "key": key,
                },
            )
        )

    @callback
    def stop_discovery() -> None:
        """Stop discovery."""
        hass.async_create_task(thread_discovery.async_stop())

    # Start Thread router discovery
    thread_discovery = discovery.ThreadRouterDiscovery(
        hass, router_discovered, router_removed
    )
    await thread_discovery.async_start()
    connection.subscriptions[msg["id"]] = stop_discovery

    connection.send_message(websocket_api.result_message(msg["id"]))
