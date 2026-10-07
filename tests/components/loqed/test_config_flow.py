"""Test the Loqed config flow."""

from collections.abc import Callable
from http import HTTPStatus
from ipaddress import ip_address
from typing import Any
from unittest.mock import Mock, patch

import aiohttp
from loqedAPI import loqed
import pytest

from homeassistant import config_entries
from homeassistant.components.loqed.const import DOMAIN
from homeassistant.const import CONF_API_TOKEN, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry, async_load_json_object_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

TEST_API_TOKEN = "eyadiuyfasiuasf"
TEST_WEBHOOK_ID = "Webhook_ID"

zeroconf_data = ZeroconfServiceInfo(
    ip_address=ip_address("192.168.12.34"),
    ip_addresses=[ip_address("192.168.12.34")],
    hostname="LOQED-ffeeddccbbaa.local",
    name="mock_name",
    port=9123,
    properties={},
    type="mock_type",
)


async def _async_init_zeroconf_flow(hass: HomeAssistant) -> dict[str, Any]:
    """Initialize a zeroconf flow and return the form result."""
    lock_result = await async_load_json_object_fixture(hass, "status_ok.json", DOMAIN)

    with patch(
        "loqedAPI.loqed.LoqedAPI.async_get_lock_details",
        return_value=lock_result,
    ):
        return await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=zeroconf_data,
        )


async def _async_init_user_flow(hass: HomeAssistant) -> dict[str, Any]:
    """Initialize a user flow and return the form result."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    return result


async def test_create_entry_zeroconf(
    hass: HomeAssistant,
    patch_lock_creation_flow: Callable[[dict[str, Any], loqed.Lock, str], Any],
) -> None:
    """Test we get can create a lock via zeroconf."""
    lock_result = await async_load_json_object_fixture(hass, "status_ok.json", DOMAIN)

    with patch(
        "loqedAPI.loqed.LoqedAPI.async_get_lock_details",
        return_value=lock_result,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=zeroconf_data,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    mock_lock = Mock(spec=loqed.Lock, id="Foo")
    webhook_id = "Webhook_ID"
    all_locks_response = await async_load_json_object_fixture(
        hass, "get_all_locks.json", DOMAIN
    )

    with patch_lock_creation_flow(all_locks_response, mock_lock, webhook_id):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_TOKEN: "eyadiuyfasiuasf",
            },
        )
        await hass.async_block_till_done()
    found_lock = all_locks_response["data"][0]

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "MyLock"
    assert result["data"] == {
        "id": "Foo",
        "lock_key_key": found_lock["key_secret"],
        "bridge_key": found_lock["bridge_key"],
        "lock_key_local_id": found_lock["local_id"],
        "bridge_mdns_hostname": found_lock["bridge_hostname"],
        "bridge_ip": found_lock["bridge_ip"],
        "name": found_lock["name"],
        CONF_WEBHOOK_ID: webhook_id,
        CONF_API_TOKEN: "eyadiuyfasiuasf",
    }
    mock_lock.getWebhooks.assert_awaited()


async def test_create_entry_user(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    patch_lock_creation_flow: Callable[[dict[str, Any], loqed.Lock, str], Any],
) -> None:
    """Test we can create a lock via manual entry."""
    result = await _async_init_user_flow(hass)

    mock_lock = Mock(spec=loqed.Lock, id="Foo")
    webhook_id = TEST_WEBHOOK_ID
    all_locks_response = await async_load_json_object_fixture(
        hass, "get_all_locks.json", DOMAIN
    )
    found_lock = all_locks_response["data"][0]

    with patch_lock_creation_flow(all_locks_response, mock_lock, webhook_id):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_TOKEN: TEST_API_TOKEN},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "MyLock"
    assert result["data"] == {
        "id": "Foo",
        "lock_key_key": found_lock["key_secret"],
        "bridge_key": found_lock["bridge_key"],
        "lock_key_local_id": found_lock["local_id"],
        "bridge_mdns_hostname": found_lock["bridge_hostname"],
        "bridge_ip": found_lock["bridge_ip"],
        "name": found_lock["name"],
        CONF_WEBHOOK_ID: webhook_id,
        CONF_API_TOKEN: TEST_API_TOKEN,
    }
    mock_lock.getWebhooks.assert_awaited()


async def test_create_entry_user_with_pick_lock(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    patch_lock_creation_flow: Callable[[dict[str, Any], loqed.Lock, str], Any],
) -> None:
    """Test we can create a lock via manual entry when multiple locks exist."""
    result = await _async_init_user_flow(hass)

    mock_lock = Mock(spec=loqed.Lock, id="Foo")
    webhook_id = TEST_WEBHOOK_ID
    all_locks_response = await async_load_json_object_fixture(
        hass, "get_all_locks.json", DOMAIN
    )
    second_lock = all_locks_response["data"][0].copy()
    second_lock["id"] = "Bar"
    second_lock["name"] = "MyOtherLock"
    all_locks_response["data"].append(second_lock)

    with patch_lock_creation_flow(all_locks_response, mock_lock, webhook_id):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_TOKEN: TEST_API_TOKEN},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pick_lock"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"lock_id": second_lock["id"]},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == second_lock["name"]
    assert result["data"] == {
        "id": second_lock["id"],
        "lock_key_key": second_lock["key_secret"],
        "bridge_key": second_lock["bridge_key"],
        "lock_key_local_id": second_lock["local_id"],
        "bridge_mdns_hostname": second_lock["bridge_hostname"],
        "bridge_ip": second_lock["bridge_ip"],
        "name": second_lock["name"],
        CONF_WEBHOOK_ID: webhook_id,
        CONF_API_TOKEN: TEST_API_TOKEN,
    }
    mock_lock.getWebhooks.assert_awaited()


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(aiohttp.ClientError, id="client_error"),
        pytest.param(TimeoutError, id="timeout"),
    ],
)
async def test_zeroconf_cannot_connect(
    hass: HomeAssistant, exception: type[Exception]
) -> None:
    """Test zeroconf discovery aborts when the bridge cannot be reached."""
    with patch("loqedAPI.loqed.LoqedAPI.async_get_lock_details", side_effect=exception):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=zeroconf_data,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_zeroconf_already_configured_updates_bridge_ip(
    hass: HomeAssistant,
) -> None:
    """Test zeroconf aborts when the bridge is configured and updates its IP."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="***REDACTED***",
        data={"bridge_ip": "10.0.0.1"},
    )
    entry.add_to_hass(hass)

    result = await _async_init_zeroconf_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data["bridge_ip"] == "192.168.12.34"


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    patch_lock_creation_flow: Callable[[dict[str, Any], loqed.Lock, str], Any],
) -> None:
    """Test the user flow aborts when the lock is already configured."""
    MockConfigEntry(domain=DOMAIN, unique_id="aabbccddeeff").add_to_hass(hass)

    result = await _async_init_user_flow(hass)

    mock_lock = Mock(spec=loqed.Lock, id="Foo")
    all_locks_response = await async_load_json_object_fixture(
        hass, "get_all_locks.json", DOMAIN
    )

    with patch_lock_creation_flow(all_locks_response, mock_lock, TEST_WEBHOOK_ID):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_TOKEN: TEST_API_TOKEN},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


def _response_error(status: HTTPStatus) -> aiohttp.ClientResponseError:
    """Create a client response error with the given status."""
    return aiohttp.ClientResponseError(Mock(), (), status=status)


CLIENT_ERRORS = [
    pytest.param(
        {"side_effect": aiohttp.ClientError}, "cannot_connect", id="client_error"
    ),
    pytest.param({"side_effect": TimeoutError}, "cannot_connect", id="timeout"),
    pytest.param(
        {"side_effect": _response_error(HTTPStatus.UNAUTHORIZED)},
        "invalid_auth",
        id="unauthorized",
    ),
    pytest.param(
        {"side_effect": _response_error(HTTPStatus.FORBIDDEN)},
        "invalid_auth",
        id="forbidden",
    ),
    pytest.param(
        {"side_effect": _response_error(HTTPStatus.INTERNAL_SERVER_ERROR)},
        "cannot_connect",
        id="server_error",
    ),
]


async def _async_complete_flow(
    hass: HomeAssistant,
    patch_lock_creation_flow: Callable[[dict[str, Any], loqed.Lock, str], Any],
    flow_id: str,
) -> None:
    """Submit the token again and assert the entry is created."""
    all_locks_response = await async_load_json_object_fixture(
        hass, "get_all_locks.json", DOMAIN
    )

    with patch_lock_creation_flow(
        all_locks_response, Mock(spec=loqed.Lock, id="Foo"), TEST_WEBHOOK_ID
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id, {CONF_API_TOKEN: TEST_API_TOKEN}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "MyLock"


@pytest.mark.parametrize(
    ("patch_kwargs", "error"),
    [
        *CLIENT_ERRORS,
        pytest.param({"return_value": {"data": []}}, "no_locks", id="no_locks"),
    ],
)
async def test_user_flow_recovers_from_cloud_error(
    hass: HomeAssistant,
    patch_lock_creation_flow: Callable[[dict[str, Any], loqed.Lock, str], Any],
    patch_kwargs: dict[str, Any],
    error: str,
) -> None:
    """Test the user flow shows a cloud error and then creates the entry."""
    result = await _async_init_user_flow(hass)

    with patch("loqedAPI.cloud_loqed.LoqedCloudAPI.async_get_locks", **patch_kwargs):
        error_result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_TOKEN: TEST_API_TOKEN}
        )

    assert error_result["type"] is FlowResultType.FORM
    assert error_result["errors"] == {"base": error}

    await _async_complete_flow(hass, patch_lock_creation_flow, result["flow_id"])


@pytest.mark.parametrize(("patch_kwargs", "error"), CLIENT_ERRORS)
async def test_user_flow_recovers_from_bridge_error(
    hass: HomeAssistant,
    patch_lock_creation_flow: Callable[[dict[str, Any], loqed.Lock, str], Any],
    patch_kwargs: dict[str, Any],
    error: str,
) -> None:
    """Test the user flow shows a bridge error and then creates the entry."""
    result = await _async_init_user_flow(hass)
    all_locks_response = await async_load_json_object_fixture(
        hass, "get_all_locks.json", DOMAIN
    )

    with (
        patch(
            "loqedAPI.cloud_loqed.LoqedCloudAPI.async_get_locks",
            return_value=all_locks_response,
        ),
        patch("loqedAPI.loqed.LoqedAPI.async_get_lock", **patch_kwargs),
    ):
        error_result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_TOKEN: TEST_API_TOKEN}
        )

    assert error_result["type"] is FlowResultType.FORM
    assert error_result["errors"] == {"base": error}

    await _async_complete_flow(hass, patch_lock_creation_flow, result["flow_id"])


async def test_pick_lock_flow_recovers_from_bridge_error(
    hass: HomeAssistant,
    patch_lock_creation_flow: Callable[[dict[str, Any], loqed.Lock, str], Any],
) -> None:
    """Test the flow recovers from a bridge error after a lock was picked."""
    result = await _async_init_user_flow(hass)
    all_locks_response = await async_load_json_object_fixture(
        hass, "get_all_locks.json", DOMAIN
    )
    second_lock = all_locks_response["data"][0].copy()
    second_lock["id"] = "Bar"
    second_lock["name"] = "MyOtherLock"
    all_locks_response["data"].append(second_lock)

    with (
        patch(
            "loqedAPI.cloud_loqed.LoqedCloudAPI.async_get_locks",
            return_value=all_locks_response,
        ),
        patch("loqedAPI.loqed.LoqedAPI.async_get_lock", side_effect=TimeoutError),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_TOKEN: TEST_API_TOKEN}
        )
        assert result["step_id"] == "pick_lock"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"lock_id": second_lock["id"]}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    with patch_lock_creation_flow(
        all_locks_response, Mock(spec=loqed.Lock, id="Foo"), TEST_WEBHOOK_ID
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_TOKEN: TEST_API_TOKEN}
        )
        assert result["step_id"] == "pick_lock"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"lock_id": second_lock["id"]}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == second_lock["name"]


@pytest.mark.parametrize(
    ("patch_kwargs", "error"),
    [
        *CLIENT_ERRORS,
        pytest.param(
            {"return_value": {"data": []}}, "lock_not_found", id="lock_not_found"
        ),
    ],
)
async def test_zeroconf_flow_recovers_from_error(
    hass: HomeAssistant,
    patch_lock_creation_flow: Callable[[dict[str, Any], loqed.Lock, str], Any],
    patch_kwargs: dict[str, Any],
    error: str,
) -> None:
    """Test the zeroconf flow shows an error and then creates the entry."""
    result = await _async_init_zeroconf_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with patch("loqedAPI.cloud_loqed.LoqedCloudAPI.async_get_locks", **patch_kwargs):
        error_result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_TOKEN: TEST_API_TOKEN}
        )

    assert error_result["type"] is FlowResultType.FORM
    assert error_result["errors"] == {"base": error}

    await _async_complete_flow(hass, patch_lock_creation_flow, result["flow_id"])


async def test_reauth_flow(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_lock_creation_flow: Callable[[dict[str, Any], loqed.Lock, str], Any],
) -> None:
    """Test reauthentication stores the new token."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    all_locks_response = await async_load_json_object_fixture(
        hass, "get_all_locks.json", DOMAIN
    )

    with patch_lock_creation_flow(
        all_locks_response, Mock(spec=loqed.Lock, id="Foo"), TEST_WEBHOOK_ID
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_TOKEN: "new_token"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[CONF_API_TOKEN] == "new_token"


@pytest.mark.parametrize(
    ("patch_kwargs", "error"),
    [
        *CLIENT_ERRORS,
        pytest.param(
            {"return_value": {"data": []}}, "lock_not_found", id="lock_not_found"
        ),
    ],
)
async def test_reauth_flow_recovers_from_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    patch_lock_creation_flow: Callable[[dict[str, Any], loqed.Lock, str], Any],
    patch_kwargs: dict[str, Any],
    error: str,
) -> None:
    """Test reauthentication shows an error and then stores the new token."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)

    with patch("loqedAPI.cloud_loqed.LoqedCloudAPI.async_get_locks", **patch_kwargs):
        error_result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_TOKEN: "new_token"}
        )

    assert error_result["type"] is FlowResultType.FORM
    assert error_result["step_id"] == "reauth_confirm"
    assert error_result["errors"] == {"base": error}

    all_locks_response = await async_load_json_object_fixture(
        hass, "get_all_locks.json", DOMAIN
    )

    with patch_lock_creation_flow(
        all_locks_response, Mock(spec=loqed.Lock, id="Foo"), TEST_WEBHOOK_ID
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_TOKEN: "new_token"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[CONF_API_TOKEN] == "new_token"
