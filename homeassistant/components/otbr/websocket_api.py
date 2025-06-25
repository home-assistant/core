"""Websocket API for OTBR."""

from collections.abc import Callable, Coroutine
from functools import wraps
from typing import TYPE_CHECKING, Any, cast

import python_otbr_api
from python_otbr_api import PENDING_DATASET_DELAY_TIMER, tlv_parser
from python_otbr_api.tlv_parser import MeshcopTLVType
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon import (
    is_multiprotocol_url,
)
from homeassistant.components.thread import async_add_dataset, async_get_dataset
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .const import DEFAULT_CHANNEL, DOMAIN
from .util import (
    OTBRData,
    compose_default_network_name,
    generate_random_pan_id,
    get_allowed_channel,
    update_issues,
)

if TYPE_CHECKING:
    from . import OTBRConfigEntry


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the OTBR Websocket API."""
    websocket_api.async_register_command(hass, websocket_info)
    websocket_api.async_register_command(hass, websocket_create_network)
    websocket_api.async_register_command(hass, websocket_set_channel)
    websocket_api.async_register_command(hass, websocket_set_network)


@websocket_api.websocket_command(
    {
        "type": "otbr/info",
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_info(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Get OTBR info."""
    config_entries: list[OTBRConfigEntry]
    config_entries = hass.config_entries.async_loaded_entries(DOMAIN)

    if not config_entries:
        connection.send_error(msg["id"], "not_loaded", "No OTBR API loaded")
        return

    response: dict[str, dict[str, Any]] = {}

    for config_entry in config_entries:
        data = config_entry.runtime_data
        try:
            border_agent_id = await data.get_border_agent_id()
            dataset = await data.get_active_dataset()
            dataset_tlvs = await data.get_active_dataset_tlvs()
            extended_address = (await data.get_extended_address()).hex()
        except HomeAssistantError as exc:
            connection.send_error(msg["id"], "otbr_info_failed", str(exc))
            return

        # The border agent ID is checked when the OTBR config entry is setup,
        # we can assert it's not None
        assert border_agent_id is not None

        extended_pan_id = (
            dataset.extended_pan_id.lower()
            if dataset and dataset.extended_pan_id
            else None
        )
        response[extended_address] = {
            "active_dataset_tlvs": dataset_tlvs.hex() if dataset_tlvs else None,
            "border_agent_id": border_agent_id.hex(),
            "channel": dataset.channel if dataset else None,
            "extended_address": extended_address,
            "extended_pan_id": extended_pan_id,
            "url": data.url,
        }

    connection.send_result(msg["id"], response)


def async_get_otbr_data(
    orig_func: Callable[
        [HomeAssistant, websocket_api.ActiveConnection, dict, OTBRData],
        Coroutine[Any, Any, None],
    ],
) -> Callable[
    [HomeAssistant, websocket_api.ActiveConnection, dict], Coroutine[Any, Any, None]
]:
    """Decorate function to get OTBR data."""

    @wraps(orig_func)
    async def async_check_extended_address_func(
        hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
    ) -> None:
        """Fetch OTBR data and pass to orig_func."""
        config_entries: list[OTBRConfigEntry]
        config_entries = hass.config_entries.async_loaded_entries(DOMAIN)

        if not config_entries:
            connection.send_error(msg["id"], "not_loaded", "No OTBR API loaded")
            return

        for config_entry in config_entries:
            data = config_entry.runtime_data
            try:
                extended_address = await data.get_extended_address()
            except HomeAssistantError as exc:
                connection.send_error(
                    msg["id"], "get_extended_address_failed", str(exc)
                )
                return
            if extended_address.hex() != msg["extended_address"]:
                continue

            await orig_func(hass, connection, msg, data)
            return

        connection.send_error(msg["id"], "unknown_router", "")

    return async_check_extended_address_func


@websocket_api.websocket_command(
    {
        "type": "otbr/create_network",
        vol.Required("extended_address"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
@async_get_otbr_data
async def websocket_create_network(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
    data: OTBRData,
) -> None:
    """Create a new Thread network."""
    channel = await get_allowed_channel(hass, data.url) or DEFAULT_CHANNEL

    try:
        await data.set_enabled(False)
    except HomeAssistantError as exc:
        connection.send_error(msg["id"], "set_enabled_failed", str(exc))
        return

    try:
        await data.factory_reset(hass)
    except HomeAssistantError as exc:
        connection.send_error(msg["id"], "factory_reset_failed", str(exc))
        return

    pan_id = generate_random_pan_id()
    try:
        await data.create_active_dataset(
            python_otbr_api.ActiveDataSet(
                channel=channel,
                network_name=compose_default_network_name(pan_id),
                pan_id=pan_id,
            )
        )
    except HomeAssistantError as exc:
        connection.send_error(msg["id"], "create_active_dataset_failed", str(exc))
        return

    try:
        await data.set_enabled(True)
    except HomeAssistantError as exc:
        connection.send_error(msg["id"], "set_enabled_failed", str(exc))
        return

    try:
        dataset_tlvs = await data.get_active_dataset_tlvs()
    except HomeAssistantError as exc:
        connection.send_error(msg["id"], "get_active_dataset_tlvs_failed", str(exc))
        return
    if not dataset_tlvs:
        connection.send_error(msg["id"], "get_active_dataset_tlvs_empty", "")
        return

    await async_add_dataset(hass, DOMAIN, dataset_tlvs.hex())

    # Update repair issues
    await update_issues(hass, data, dataset_tlvs)

    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        "type": "otbr/set_network",
        vol.Required("extended_address"): str,
        vol.Required("dataset_id"): str,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
@async_get_otbr_data
async def websocket_set_network(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
    data: OTBRData,
) -> None:
    """Set the Thread network to be used by the OTBR."""
    dataset_tlv = await async_get_dataset(hass, msg["dataset_id"])

    if not dataset_tlv:
        connection.send_error(msg["id"], "unknown_dataset", "Unknown dataset")
        return
    dataset = tlv_parser.parse_tlv(dataset_tlv)
    if channel := dataset.get(MeshcopTLVType.CHANNEL):
        thread_dataset_channel = cast(tlv_parser.Channel, channel).channel

    allowed_channel = await get_allowed_channel(hass, data.url)

    if allowed_channel and thread_dataset_channel != allowed_channel:
        connection.send_error(
            msg["id"],
            "channel_conflict",
            f"Can't connect to network on channel {thread_dataset_channel}, ZHA is "
            f"using channel {allowed_channel}",
        )
        return

    try:
        await data.set_enabled(False)
    except HomeAssistantError as exc:
        connection.send_error(msg["id"], "set_enabled_failed", str(exc))
        return

    try:
        await data.set_active_dataset_tlvs(bytes.fromhex(dataset_tlv))
    except HomeAssistantError as exc:
        connection.send_error(msg["id"], "set_active_dataset_tlvs_failed", str(exc))
        return

    try:
        await data.set_enabled(True)
    except HomeAssistantError as exc:
        connection.send_error(msg["id"], "set_enabled_failed", str(exc))
        return

    # Update repair issues
    await update_issues(hass, data, bytes.fromhex(dataset_tlv))

    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        "type": "otbr/set_channel",
        vol.Required("extended_address"): str,
        vol.Required("channel"): int,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
@async_get_otbr_data
async def websocket_set_channel(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
    data: OTBRData,
) -> None:
    """Set current channel."""
    if is_multiprotocol_url(data.url):
        connection.send_error(
            msg["id"],
            "multiprotocol_enabled",
            "Channel change not allowed when in multiprotocol mode",
        )
        return

    channel: int = msg["channel"]
    delay: float = PENDING_DATASET_DELAY_TIMER / 1000

    try:
        await data.set_channel(channel)
    except HomeAssistantError as exc:
        connection.send_error(msg["id"], "set_channel_failed", str(exc))
        return

    connection.send_result(msg["id"], {"delay": delay})
