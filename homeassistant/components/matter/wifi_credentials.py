"""Wi-Fi credentials of Matter network infrastructure managers.

A manager with the Wi-Fi Network Management cluster hands the passphrase of
the network it runs to a fabric member with the Manage privilege. The user
imports it with the manager's button, for the Matter server to commission
Wi-Fi devices onto that network.
"""

from base64 import b64decode
from typing import TYPE_CHECKING, Any

from chip.clusters import Objects as clusters
from matter_server.client.exceptions import MatterClientException
from matter_server.common.errors import MatterError
from matter_server.common.helpers.util import create_attribute_path

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from matter_server.client import MatterClient
    from matter_server.client.models.node import MatterEndpoint


def _passphrase_from_response(response: Any) -> str:
    """Return the passphrase of a NetworkPassphraseResponse; raise ValueError without one."""
    raw = response.get("passphrase") if isinstance(response, dict) else None
    if not isinstance(raw, str) or not (passphrase := b64decode(raw, validate=True)):
        raise ValueError("response carries no passphrase")
    return passphrase.decode()


def _unusable() -> HomeAssistantError:
    return HomeAssistantError(
        translation_domain=DOMAIN, translation_key="wifi_credentials_unusable"
    )


def _import_failed(err: MatterError | MatterClientException) -> HomeAssistantError:
    return HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="wifi_credentials_import_failed",
        translation_placeholders={"error": str(err) or err.__class__.__name__},
    )


def _ssid_of(value: Any) -> bytes | None:
    """Return the SSID a read answered with; None without one."""
    if not isinstance(value, str):
        return None
    try:
        return b64decode(value, validate=True) or None
    except ValueError as err:
        raise _unusable() from err


async def _async_read_network(
    matter_client: MatterClient, endpoint: MatterEndpoint
) -> tuple[bytes | None, Any]:
    """Read the SSID a manager shares and its passphrase surrogate from it.

    The cache may lag a change. The surrogate changes with the passphrase.
    """
    attributes = clusters.WiFiNetworkManagement.Attributes
    ssid_path, surrogate_path = (
        create_attribute_path(
            endpoint.endpoint_id,
            clusters.WiFiNetworkManagement.id,
            attribute.attribute_id,
        )
        for attribute in (attributes.Ssid, attributes.PassphraseSurrogate)
    )
    try:
        values = await matter_client.read_attribute(
            endpoint.node.node_id, [ssid_path, surrogate_path]
        )
    except (MatterError, MatterClientException) as err:
        raise _import_failed(err) from err
    return _ssid_of(values.get(ssid_path)), values.get(surrogate_path)


async def async_import_credentials(
    matter_client: MatterClient, endpoint: MatterEndpoint
) -> None:
    """Hand the Wi-Fi network a manager runs to the Matter server."""
    # Null while sharing is off or the manager runs no network.
    ssid, surrogate = await _async_read_network(matter_client, endpoint)
    if ssid is None:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="wifi_network_not_shared"
        )
    try:
        network = ssid.decode()
    except UnicodeDecodeError as err:
        raise _unusable() from err
    # Mandatory with a network shared; without it, a passphrase changed
    # meanwhile could not be told.
    if not isinstance(surrogate, int):
        raise _unusable()
    try:
        response: Any = await matter_client.send_device_command(
            node_id=endpoint.node.node_id,
            endpoint_id=endpoint.endpoint_id,
            command=clusters.WiFiNetworkManagement.Commands.NetworkPassphraseRequest(),
        )
    except (MatterError, MatterClientException) as err:
        raise _import_failed(err) from err
    try:
        passphrase = _passphrase_from_response(response)
    except ValueError as err:
        raise _unusable() from err
    # Stored only if neither the network nor its passphrase changed meanwhile.
    if await _async_read_network(matter_client, endpoint) != (ssid, surrogate):
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="wifi_network_changed"
        )
    try:
        await matter_client.set_wifi_credentials(ssid=network, credentials=passphrase)
    except (MatterError, MatterClientException) as err:
        raise _import_failed(err) from err

    LOGGER.debug(
        "Imported Wi-Fi credentials from node %s endpoint %s",
        endpoint.node.node_id,
        endpoint.endpoint_id,
    )
