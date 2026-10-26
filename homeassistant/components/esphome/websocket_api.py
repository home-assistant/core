"""ESPHome websocket API."""

from typing import Any, cast

from aioesphomeapi import APIConnectionError, WizardEntityField, build_device_unique_id
from aioesphomeapi.model import SendspinPairingTokenStatus
import probatio

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import CONF_NOISE_PSK, DOMAIN
from .entry_data import INFO_TYPE_TO_PLATFORM, ESPHomeConfigEntry, RuntimeEntryData
from .sendspin import (
    async_sendspin_client_ids,
    async_sendspin_entry_data,
    async_subscribe_sendspin_clients,
)
from .serial_proxy import build_url

TYPE = "type"
ENTRY_ID = "entry_id"
DEVICE_ID = "device_id"
CLIENT_ID = "client_id"
CLIENT_IDS = "client_ids"

ZWAVE_JS_DOMAIN = "zwave_js"

_UNAVAILABLE_CAPABILITIES: dict[str, Any] = {
    "bluetooth_proxy": {"supported": False},
    "zwave_proxy": {"supported": False, "home_id": 0, "config_entry_id": None},
    "serial_proxies": [],
    "sendspin": {"supported": False},
}


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the websocket API."""
    websocket_api.async_register_command(hass, get_encryption_key)
    websocket_api.async_register_command(hass, get_device_capabilities)
    websocket_api.async_register_command(hass, get_device_wizard)
    websocket_api.async_register_command(hass, subscribe_sendspin_clients)
    websocket_api.async_register_command(hass, get_sendspin_pairing_token)


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required(TYPE): "esphome/get_encryption_key",
        probatio.Required(ENTRY_ID): str,
    }
)
def get_encryption_key(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get the encryption key for an ESPHome config entry."""
    entry = hass.config_entries.async_get_entry(msg[ENTRY_ID])
    if entry is None:
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "Config entry not found"
        )
        return

    connection.send_result(
        msg["id"],
        {
            "encryption_key": entry.data.get(CONF_NOISE_PSK),
        },
    )


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required(TYPE): "esphome/get_device_capabilities",
        probatio.Required(DEVICE_ID): str,
    }
)
def get_device_capabilities(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the cached ESPHome device capabilities for the device page."""
    if (entry := _async_get_main_device_entry(hass, connection, msg)) is None:
        return

    capabilities = None
    if entry.state is ConfigEntryState.LOADED:
        capabilities = entry.runtime_data.device_capabilities

    # Unknown until the first connect after an upgrade
    if capabilities is None:
        connection.send_result(msg["id"], _UNAVAILABLE_CAPABILITIES)
        return

    home_id = capabilities.zwave_proxy.home_id
    connection.send_result(
        msg["id"],
        {
            "bluetooth_proxy": {
                "supported": bool(capabilities.bluetooth_proxy.feature_flags),
            },
            "zwave_proxy": {
                "supported": bool(capabilities.zwave_proxy.feature_flags),
                "home_id": home_id,
                "config_entry_id": _zwave_js_config_entry_id(hass, home_id),
            },
            "serial_proxies": [
                {
                    "name": proxy.name,
                    "port_type": (
                        proxy.port_type.name if proxy.port_type is not None else None
                    ),
                    "url": str(build_url(entry.entry_id, port_name=proxy.name)),
                }
                for proxy in capabilities.serial_proxies
            ],
            "sendspin": {"supported": bool(capabilities.sendspin.feature_flags)},
        },
    )


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required(TYPE): "esphome/get_device_wizard",
        probatio.Required(DEVICE_ID): str,
    }
)
def get_device_wizard(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the cached ESPHome device wizard, with the entity ids it lists."""
    if (entry := _async_get_main_device_entry(hass, connection, msg)) is None:
        return

    wizard = None
    if entry.state is ConfigEntryState.LOADED:
        wizard = entry.runtime_data.device_wizard

    if wizard is None:
        connection.send_result(msg["id"], {"pages": []})
        return

    entry_data = entry.runtime_data
    ent_reg = er.async_get(hass)
    connection.send_result(
        msg["id"],
        {
            "pages": [
                {
                    "title": page.title,
                    "description": page.description,
                    "entities": [
                        {
                            "entity_id": _wizard_entity_id(ent_reg, entry_data, entity),
                            "description": entity.description,
                        }
                        for entity in page.entities
                    ],
                }
                for page in wizard.pages
            ]
        },
    )


@callback
def _async_get_main_device_entry(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> ESPHomeConfigEntry | None:
    """Return the config entry of the requested main ESPHome device, or send an error."""
    device, candidate = dr.async_get_device_and_config_entry_for_domain(
        hass, msg[DEVICE_ID], domain=DOMAIN, include_child_devices=False
    )
    if device is None:
        connection.send_error(
            msg["id"], websocket_api.ERR_NOT_FOUND, "Device not found"
        )
        return None

    if candidate is None:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_NOT_FOUND,
            "Device is not an ESPHome device",
        )
        return None

    if not _is_main_esphome_device(device):
        connection.send_error(
            msg["id"],
            websocket_api.ERR_NOT_FOUND,
            "Device is not the main ESPHome device",
        )
        return None
    return cast(ESPHomeConfigEntry, candidate)


def _wizard_entity_id(
    ent_reg: er.EntityRegistry,
    entry_data: RuntimeEntryData,
    entity: WizardEntityField,
) -> str | None:
    """Return the entity id of an entity the wizard lists, if it has one."""
    assert entry_data.device_info is not None
    key = (entity.device_id, entity.key)
    # Keys are only unique per platform and the wizard does not name the platform
    matches = [
        (info_type, infos[key])
        for info_type, infos in entry_data.info.items()
        if key in infos
    ]
    if len(matches) != 1:
        return None
    info_type, info = matches[0]
    return ent_reg.async_get_entity_id(
        INFO_TYPE_TO_PLATFORM[info_type],
        DOMAIN,
        build_device_unique_id(entry_data.device_info.mac_address, info),
    )


def _is_main_esphome_device(device: dr.DeviceEntry) -> bool:
    """Return True if device is the MAC-connected ESPHome node."""
    return any(
        conn_type == dr.CONNECTION_NETWORK_MAC for conn_type, _ in device.connections
    )


def _zwave_js_config_entry_id(hass: HomeAssistant, home_id: int) -> str | None:
    """Return the entry ID of the zwave_js entry whose unique ID is this home ID."""
    if not home_id:
        return None
    home_id_str = str(home_id)
    # Ignored and disabled entries are not the configured network. Scan all
    # matches because the unique ID index returns only the first one, and
    # compare with str() so legacy integer unique IDs still match.
    for entry in hass.config_entries.async_entries(
        ZWAVE_JS_DOMAIN,
        include_ignore=False,
        include_disabled=False,
    ):
        if str(entry.unique_id) == home_id_str:
            return entry.entry_id
    return None


@websocket_api.require_admin
@websocket_api.websocket_command(
    {probatio.Required(TYPE): "sendspin/subscribe_clients"}
)
@callback
def subscribe_sendspin_clients(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Stream the Sendspin client ids a pairing token can be fetched for.

    A Sendspin server (Music Assistant) gets the ids of the connected devices
    right away and again whenever they change, and asks for a token with
    sendspin/get_pairing_token when one of them is a client it has not paired.
    """

    @callback
    def _send(client_ids: list[str]) -> None:
        connection.send_event(msg["id"], {CLIENT_IDS: client_ids})

    connection.subscriptions[msg["id"]] = async_subscribe_sendspin_clients(hass, _send)
    connection.send_result(msg["id"])
    _send(async_sendspin_client_ids(hass))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required(TYPE): "sendspin/get_pairing_token",
        probatio.Required(CLIENT_ID): str,
    }
)
@websocket_api.async_response
async def get_sendspin_pairing_token(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the Sendspin pairing token of the device with this Sendspin client id.

    The token is fetched fresh from the device every time.
    """
    if (entry_data := async_sendspin_entry_data(hass, msg[CLIENT_ID])) is None:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_NOT_FOUND,
            "No connected ESPHome device has this Sendspin client id",
        )
        return
    try:
        response = await entry_data.client.sendspin_pairing_token()
    except APIConnectionError as err:
        connection.send_error(
            msg["id"],
            websocket_api.ERR_UNKNOWN_ERROR,
            f"{entry_data.name} did not answer: {err}",
        )
        return
    if (status := response.status) is not SendspinPairingTokenStatus.OK:
        # None is a status newer firmware added that this library does not know
        reason = (
            "unknown status"
            if status is None
            else status.name.lower().replace("_", " ")
        )
        connection.send_error(
            msg["id"],
            websocket_api.ERR_UNKNOWN_ERROR,
            f"{entry_data.name} hands out no pairing token: {reason}",
        )
        return
    # The token is a long-lived secret: handed over, never stored
    connection.send_result(msg["id"], {"token": response.token})
