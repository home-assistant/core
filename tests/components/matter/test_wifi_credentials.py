"""Test the Wi-Fi credentials import from Matter network managers."""

from base64 import b64encode
from typing import Any
from unittest.mock import MagicMock

from chip.clusters import Objects as clusters
from chip.clusters.Types import NullValue
from matter_server.client.exceptions import NotConnected
from matter_server.client.models import device_types
from matter_server.common.errors import NodeNotReady, UnknownError
import pytest
from pytest_homeassistant.common import MockUser

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
)
from homeassistant.helpers import entity_registry as er

from .common import setup_integration_with_node_fixture

SSID = "TestNetwork"
PASSPHRASE = "correct horse battery staple"


def _response(passphrase: bytes) -> dict[str, str]:
    """Return a NetworkPassphraseResponse as the client delivers it."""
    return {"passphrase": b64encode(passphrase).decode()}


def _passphrase_reads(matter_client: MagicMock) -> int:
    """Return how often the passphrase was requested."""
    return sum(
        isinstance(
            call.kwargs.get("command"),
            clusters.WiFiNetworkManagement.Commands.NetworkPassphraseRequest,
        )
        for call in matter_client.send_device_command.call_args_list
    )


def _import_button(hass: HomeAssistant) -> str | None:
    """Return the entity id of the import button, if there is one."""
    return next(
        (
            entry.entity_id
            for entry in er.async_get(hass).entities.values()
            if entry.platform == "matter"
            and "WifiCredentialsImportButton" in entry.unique_id
        ),
        None,
    )


async def _press_import(hass: HomeAssistant, context: Context | None = None) -> None:
    """Press the import button."""
    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: _import_button(hass)},
        blocking=True,
        context=context,
    )


@pytest.fixture(autouse=True)
def answer_reads_from_the_cache(matter_client: MagicMock) -> None:
    """Have a manager answer reads with what it reported last."""

    async def read(node_id: int, attribute_path: str | list[str]) -> dict[str, Any]:
        attributes = matter_client.get_node(node_id).node_data.attributes
        paths = [attribute_path] if isinstance(attribute_path, str) else attribute_path
        return {path: attributes.get(path) for path in paths}

    matter_client.read_attribute.side_effect = read


@pytest.fixture(name="passphrase_response")
def passphrase_response_fixture(matter_client: MagicMock) -> dict[str, str]:
    """Make NetworkPassphraseRequest return PASSPHRASE."""
    response = _response(PASSPHRASE.encode())
    matter_client.send_device_command.return_value = response
    return response


@pytest.mark.usefixtures("passphrase_response")
async def test_manager_is_not_read_without_a_press(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """The passphrase is privileged and only read when the user asks."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    await hass.async_block_till_done()

    assert _passphrase_reads(matter_client) == 0
    matter_client.set_wifi_credentials.assert_not_awaited()


@pytest.mark.usefixtures("passphrase_response")
async def test_pressing_the_button_imports_the_credentials(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """The button reads the passphrase and hands the network to the server."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )

    await _press_import(hass)

    assert _passphrase_reads(matter_client) == 1
    assert matter_client.send_device_command.call_args.kwargs["node_id"] == 90
    assert matter_client.send_device_command.call_args.kwargs["endpoint_id"] == 1
    matter_client.set_wifi_credentials.assert_awaited_once_with(
        ssid=SSID, credentials=PASSPHRASE
    )


@pytest.mark.usefixtures("passphrase_response")
async def test_only_an_administrator_imports_the_credentials(
    hass: HomeAssistant,
    matter_client: MagicMock,
    hass_admin_user: MockUser,
    non_admin_user: MockUser,
) -> None:
    """The import replaces the server's credentials, which only an administrator sets."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )

    with pytest.raises(Unauthorized):
        await _press_import(hass, Context(user_id=non_admin_user.id))
    assert _passphrase_reads(matter_client) == 0

    await _press_import(hass, Context(user_id=hass_admin_user.id))
    matter_client.set_wifi_credentials.assert_awaited_once_with(
        ssid=SSID, credentials=PASSPHRASE
    )


async def test_no_import_button_on_a_thread_border_router(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """Only a network infrastructure manager shares its Wi-Fi network."""
    await setup_integration_with_node_fixture(
        hass,
        "thread_border_router",
        matter_client,
        override_attributes={
            "1/29/0": [{"0": device_types.ThreadBorderRouter.device_type, "1": 1}]
        },
    )

    assert _import_button(hass) is None


async def test_no_import_button_without_the_cluster(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A node without the Wi-Fi Network Management cluster has no import button."""
    await setup_integration_with_node_fixture(hass, "eve_contact_sensor", matter_client)

    assert _import_button(hass) is None


@pytest.mark.parametrize("ssid", [NullValue, ""])
@pytest.mark.usefixtures("passphrase_response")
async def test_a_manager_sharing_no_network_is_not_read(
    hass: HomeAssistant, matter_client: MagicMock, ssid: object
) -> None:
    """Sharing switched off reads as no SSID; the press fails without a read."""
    await setup_integration_with_node_fixture(
        hass,
        "thread_border_router",
        matter_client,
        override_attributes={"1/1105/0": ssid},
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await _press_import(hass)

    assert exc_info.value.translation_key == "wifi_network_not_shared"
    assert _passphrase_reads(matter_client) == 0
    matter_client.set_wifi_credentials.assert_not_awaited()


@pytest.mark.parametrize(
    "response",
    [
        None,
        {"passphrase": None},
        {"passphrase": ""},
        {"passphrase": "%%%not-base64%%%"},
        _response(b"\xff\xfe"),
    ],
)
async def test_an_unusable_response_fails_the_press(
    hass: HomeAssistant,
    matter_client: MagicMock,
    response: dict[str, str | None] | None,
) -> None:
    """A response without a readable passphrase is reported, nothing imported."""
    matter_client.send_device_command.return_value = response
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await _press_import(hass)

    assert exc_info.value.translation_key == "wifi_credentials_unusable"
    matter_client.set_wifi_credentials.assert_not_awaited()


@pytest.mark.parametrize("ssid", [b64encode(b"\xff\xfe").decode(), "%%%not-base64%%%"])
@pytest.mark.usefixtures("passphrase_response")
async def test_an_ssid_that_is_not_text_is_not_read(
    hass: HomeAssistant, matter_client: MagicMock, ssid: str
) -> None:
    """The Matter server takes the SSID as text; another one fails the press."""
    await setup_integration_with_node_fixture(
        hass,
        "thread_border_router",
        matter_client,
        override_attributes={"1/1105/0": ssid},
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await _press_import(hass)

    assert exc_info.value.translation_key == "wifi_credentials_unusable"
    assert _passphrase_reads(matter_client) == 0


@pytest.mark.usefixtures("passphrase_response")
async def test_a_manager_without_a_passphrase_surrogate_is_not_read(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """Without the surrogate, a passphrase changed during the read goes unnoticed."""
    await setup_integration_with_node_fixture(
        hass,
        "thread_border_router",
        matter_client,
        override_attributes={"1/1105/1": None},
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await _press_import(hass)

    assert exc_info.value.translation_key == "wifi_credentials_unusable"
    assert _passphrase_reads(matter_client) == 0


@pytest.mark.parametrize(
    "changed",
    [
        {"1/1105/0": b64encode(b"OtherNetwork").decode()},
        {"1/1105/1": 1785200000001},
    ],
    ids=["network", "passphrase"],
)
@pytest.mark.usefixtures("passphrase_response")
async def test_credentials_changed_during_the_read_are_not_stored(
    hass: HomeAssistant, matter_client: MagicMock, changed: dict[str, Any]
) -> None:
    """A passphrase answered after the network or passphrase changed is not stored."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    # The manager changed while the passphrase was asked for, before it
    # reported that.
    answers = iter([{}, changed])

    async def read(node_id: int, attribute_path: list[str]) -> dict[str, Any]:
        attributes = matter_client.get_node(node_id).node_data.attributes
        return {path: attributes.get(path) for path in attribute_path} | next(answers)

    matter_client.read_attribute.side_effect = read

    with pytest.raises(HomeAssistantError) as exc_info:
        await _press_import(hass)

    assert exc_info.value.translation_key == "wifi_network_changed"
    matter_client.set_wifi_credentials.assert_not_awaited()


@pytest.mark.usefixtures("passphrase_response")
async def test_an_unreadable_network_fails_the_press(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """A manager whose network cannot be read is not asked for a passphrase."""
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )
    matter_client.read_attribute.side_effect = NotConnected()

    with pytest.raises(HomeAssistantError) as exc_info:
        await _press_import(hass)

    assert exc_info.value.translation_key == "wifi_credentials_import_failed"
    assert _passphrase_reads(matter_client) == 0


@pytest.mark.parametrize(
    ("error", "placeholder"),
    [
        (NodeNotReady("node not ready"), "node not ready"),
        (UnknownError(), "UnknownError"),
        (NotConnected(), "NotConnected"),
    ],
)
async def test_a_failed_read_fails_the_press(
    hass: HomeAssistant,
    matter_client: MagicMock,
    error: Exception,
    placeholder: str,
) -> None:
    """A read the server fails is reported to the user, with the server's reason."""
    matter_client.send_device_command.side_effect = error
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await _press_import(hass)

    assert exc_info.value.translation_key == "wifi_credentials_import_failed"
    assert exc_info.value.translation_placeholders == {"error": placeholder}
    matter_client.set_wifi_credentials.assert_not_awaited()


@pytest.mark.usefixtures("passphrase_response")
async def test_a_failed_store_fails_the_press(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """Credentials the server does not store are reported to the user."""
    matter_client.set_wifi_credentials.side_effect = UnknownError("store failed")
    await setup_integration_with_node_fixture(
        hass, "thread_border_router", matter_client
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await _press_import(hass)

    assert exc_info.value.translation_key == "wifi_credentials_import_failed"
    assert exc_info.value.translation_placeholders == {"error": "store failed"}


async def test_set_wifi_credentials_action(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """The action hands the credentials to the Matter server."""
    await setup_integration_with_node_fixture(hass, "eve_contact_sensor", matter_client)

    await hass.services.async_call(
        "matter",
        "set_wifi_credentials",
        {"ssid": "IoT", "password": "hunter2hunter2"},
        blocking=True,
    )

    matter_client.set_wifi_credentials.assert_awaited_once_with(
        ssid="IoT", credentials="hunter2hunter2"
    )


async def test_set_wifi_credentials_action_failure(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """Credentials the server does not store fail the action."""
    matter_client.set_wifi_credentials.side_effect = NotConnected()
    await setup_integration_with_node_fixture(hass, "eve_contact_sensor", matter_client)

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            "matter",
            "set_wifi_credentials",
            {"ssid": "IoT", "password": "hunter2hunter2"},
            blocking=True,
        )

    assert exc_info.value.translation_key == "wifi_credentials_set_failed"
    assert exc_info.value.translation_placeholders == {"error": "NotConnected"}


async def test_set_wifi_credentials_action_without_matter(
    hass: HomeAssistant, matter_client: MagicMock
) -> None:
    """The action explains that Matter is not loaded."""
    await setup_integration_with_node_fixture(hass, "eve_contact_sensor", matter_client)
    entry = hass.config_entries.async_entries("matter")[0]
    await hass.config_entries.async_unload(entry.entry_id)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            "matter",
            "set_wifi_credentials",
            {"ssid": "IoT", "password": "hunter2hunter2"},
            blocking=True,
        )

    assert exc_info.value.translation_key == "matter_not_set_up"
    matter_client.set_wifi_credentials.assert_not_awaited()


async def test_set_wifi_credentials_action_is_admin_only(
    hass: HomeAssistant, matter_client: MagicMock, hass_read_only_user: MockUser
) -> None:
    """Only an administrator can change the commissioning credentials."""
    await setup_integration_with_node_fixture(hass, "eve_contact_sensor", matter_client)

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            "matter",
            "set_wifi_credentials",
            {"ssid": "IoT", "password": "hunter2hunter2"},
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )

    matter_client.set_wifi_credentials.assert_not_awaited()
