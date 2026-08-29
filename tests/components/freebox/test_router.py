"""Tests for the Freebox utility methods."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

from freebox_api.exceptions import AuthorizationError, HttpRequestError
import pytest

from homeassistant.components.freebox.router import (
    async_forget_registration,
    get_hosts_list_if_supported,
    is_invalid_token_error,
    is_json,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import slugify

from .const import (
    DATA_LAN_GET_HOSTS_LIST_MODE_BRIDGE,
    DATA_WIFI_GET_GLOBAL_CONFIG,
    MOCK_HOST,
)


@pytest.fixture(autouse=True)
def mock_path():
    """Use the real pathlib.Path in this module so file removal can be tested.

    This overrides the autouse fixture of the same name in conftest.py,
    which stubs out Path for the config flow / setup tests in this package.
    """
    return


async def test_is_json() -> None:
    """Test is_json method."""

    # Valid JSON values
    assert is_json("{}")
    assert is_json('{ "simple":"json" }')
    assert is_json(json.dumps(DATA_WIFI_GET_GLOBAL_CONFIG))
    assert is_json(json.dumps(DATA_LAN_GET_HOSTS_LIST_MODE_BRIDGE))

    # Not valid JSON values
    assert not is_json(None)
    assert not is_json("")
    assert not is_json("XXX")
    assert not is_json("{XXX}")


async def test_get_hosts_list_if_supported(
    router: Mock,
) -> None:
    """In router mode, get_hosts_list is supported and list is filled."""
    supports_hosts, fbx_devices = await get_hosts_list_if_supported(router())
    assert supports_hosts is True
    # List must not be empty; but its content depends on
    # how many unit tests are executed...
    assert fbx_devices
    # We expect 4 devices from lan_get_hosts_list.json
    # and 1 from lan_get_hosts_list_guest.json
    assert len(fbx_devices) == 5
    assert "d633d0c8-958c-43cc-e807-d881b076924b" in str(fbx_devices)
    assert "d633d0c8-958c-42cc-e807-d881b476924b" in str(fbx_devices)


async def test_get_hosts_list_if_supported_bridge(
    router_bridge_mode: Mock,
) -> None:
    """In bridge mode, get_hosts_list is NOT supported and list is empty."""
    supports_hosts, fbx_devices = await get_hosts_list_if_supported(
        router_bridge_mode()
    )
    assert supports_hosts is False
    assert fbx_devices == []


async def test_get_hosts_list_if_supported_bridge_error(
    mock_router_bridge_mode_error: Mock,
) -> None:
    """Other exceptions must be propagated."""
    with pytest.raises(HttpRequestError):
        await get_hosts_list_if_supported(mock_router_bridge_mode_error())


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        pytest.param(
            AuthorizationError(
                'Starting session failed (APIResponse: {"success": false, '
                '"error_code": "invalid_token"})'
            ),
            True,
            id="invalid_token",
        ),
        pytest.param(
            AuthorizationError(
                'Starting session failed (APIResponse: {"success": false, '
                '"error_code": "internal_error"})'
            ),
            False,
            id="other_error_code",
        ),
        pytest.param(
            AuthorizationError("Authorization timed out"),
            False,
            id="no_api_response",
        ),
        pytest.param(
            AuthorizationError("The app token is invalid or has been revoked"),
            False,
            id="denied_pairing_mentions_invalid_but_has_no_error_code",
        ),
    ],
)
def test_is_invalid_token_error(error: AuthorizationError, expected: bool) -> None:
    """Only a genuine invalid_token APIResponse must be treated as such."""
    assert is_invalid_token_error(error) is expected


async def test_async_forget_registration(hass: HomeAssistant, tmp_path: Path) -> None:
    """async_forget_registration must remove the stored app token, if any."""
    with patch("homeassistant.components.freebox.router.Store") as mock_store:
        mock_store.return_value.path = str(tmp_path)

        token_file = tmp_path / f"{slugify(MOCK_HOST)}.conf"
        token_file.write_text('{"app_token": "stale"}')
        assert token_file.exists()

        await async_forget_registration(hass, MOCK_HOST)
        assert not token_file.exists()

        # Calling again with no stored file left must not raise.
        await async_forget_registration(hass, MOCK_HOST)
