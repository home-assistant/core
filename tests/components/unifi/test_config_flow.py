"""Test UniFi Network config flow."""

import asyncio
from collections.abc import Callable
import json
import socket
from typing import Any
from unittest.mock import patch

import aiounifi
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant import config_entries
from homeassistant.components.unifi.config_flow import _async_discover_unifi
from homeassistant.components.unifi.const import (
    CONF_ALLOW_BANDWIDTH_SENSORS,
    CONF_ALLOW_UPTIME_SENSORS,
    CONF_BLOCK_CLIENT,
    CONF_CLIENT_SOURCE,
    CONF_CONNECTION_MODE,
    CONF_DETECTION_TIME,
    CONF_DPI_RESTRICTIONS,
    CONF_IGNORE_LOCAL_MAC,
    CONF_IGNORE_WIRED_BUG,
    CONF_MORE_OPTIONS,
    CONF_SITE_ID,
    CONF_SSID_FILTER,
    CONF_TRACK_CLIENTS,
    CONF_TRACK_DEVICES,
    CONF_TRACK_WIRED_CLIENTS,
    CONNECTION_MODE_API_KEY_ONLY,
    DOMAIN,
)
from homeassistant.components.unifi.errors import (
    AuthenticationRequired,
    CannotConnect,
    MfaRequired,
)
from homeassistant.config_entries import ConfigEntryState, ConfigFlowResult
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import format_mac

from .conftest import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_SITE,
    NETWORK_API_KEY,
    NETWORK_SITE_ID,
    NETWORK_URL,
    ConfigEntryFactoryType,
    network_page,
)

CLIENTS = [{"mac": "00:00:00:00:00:01"}]

DEVICES = [
    {
        "board_rev": 21,
        "device_id": "mock-id",
        "ip": "10.0.1.1",
        "last_seen": 0,
        "mac": "00:00:00:00:01:01",
        "model": "U7PG2",
        "name": "access_point",
        "state": 1,
        "type": "uap",
        "version": "4.0.80.10875",
        "wlan_overrides": [
            {
                "name": "SSID 3",
                "radio": "na",
                "radio_name": "wifi1",
                "wlan_id": "012345678910111213141516",
            },
            {
                "name": "",
                "radio": "na",
                "radio_name": "wifi1",
                "wlan_id": "012345678910111213141516",
            },
            {
                "radio": "na",
                "radio_name": "wifi1",
                "wlan_id": "012345678910111213141516",
            },
        ],
    }
]

WLANS = [
    {"_id": "1", "name": "SSID 1", "enabled": True},
    {
        "_id": "2",
        "name": "SSID 2",
        "name_combine_enabled": False,
        "name_combine_suffix": "_IOT",
        "enabled": True,
    },
    {"_id": "3", "name": "SSID 4", "name_combine_enabled": False, "enabled": True},
]

DPI_GROUPS = [
    {
        "_id": "5ba29dd8e3c58f026e9d7c4a",
        "name": "Default",
        "site_id": "5ba29dd4e3c58f026e9d7c38",
    },
]

OLD_SITE_ID = "5f0a1b2c3d4e5f6a7b8c9d0e"
NEW_SITE_ID = "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"


async def _select_menu(
    hass: HomeAssistant, result: ConfigFlowResult, next_step_id: str
) -> ConfigFlowResult:
    """Pick a menu option of a flow."""
    assert result["type"] is FlowResultType.MENU
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": next_step_id}
    )


async def _start_user_flow(hass: HomeAssistant, next_step_id: str) -> ConfigFlowResult:
    """Start a user flow and pick how to connect."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    return await _select_menu(hass, result, next_step_id)


@pytest.mark.usefixtures("mock_default_requests")
async def test_flow_works(hass: HomeAssistant, mock_discovery) -> None:
    """Test config flow."""
    mock_discovery.return_value = "1"
    result = await _start_user_flow(hass, "full")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "full"
    assert result["data_schema"]({CONF_PASSWORD: ""}) == {
        CONF_HOST: "1",
        CONF_USERNAME: "",
        CONF_PASSWORD: "",
        CONF_PORT: 443,
        CONF_VERIFY_SSL: False,
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "1.2.3.4",
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
            CONF_PORT: 1234,
            CONF_VERIFY_SSL: True,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Site name"
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
        CONF_USERNAME: "username",
        CONF_PASSWORD: "password",
        CONF_PORT: 1234,
        CONF_SITE_ID: "site_id",
        CONF_VERIFY_SSL: True,
    }
    assert result["result"].unique_id == "1"


async def test_flow_works_negative_discovery(hass: HomeAssistant) -> None:
    """Test config flow with a negative outcome of async_discovery_unifi."""
    result = await _start_user_flow(hass, "full")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "full"
    assert result["data_schema"]({CONF_PASSWORD: ""}) == {
        CONF_HOST: "unifi",
        CONF_USERNAME: "",
        CONF_PASSWORD: "",
        CONF_PORT: 443,
        CONF_VERIFY_SSL: False,
    }


@pytest.mark.parametrize(
    "site_payload",
    [
        [
            {"name": "default", "role": "admin", "desc": "site name", "_id": "1"},
            {"name": "site2", "role": "admin", "desc": "site2 name", "_id": "2"},
        ]
    ],
)
@pytest.mark.usefixtures("mock_default_requests")
async def test_flow_multiple_sites(hass: HomeAssistant) -> None:
    """Test config flow works when finding multiple sites."""
    result = await _start_user_flow(hass, "full")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "full"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "1.2.3.4",
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
            CONF_PORT: 1234,
            CONF_VERIFY_SSL: True,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "site"
    assert result["data_schema"]({"site": "1"})
    assert result["data_schema"]({"site": "2"})


@pytest.mark.usefixtures("config_entry_setup")
async def test_flow_raise_already_configured(hass: HomeAssistant) -> None:
    """Test config flow aborts since a connected config entry already exists."""
    result = await _start_user_flow(hass, "full")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "full"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "1.2.3.4",
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
            CONF_PORT: 1234,
            CONF_VERIFY_SSL: True,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


GET_UNIFI_API = "homeassistant.components.unifi.config_flow.get_unifi_api"
SITES_UPDATE = "aiounifi.interfaces.sites.Sites.update"


@pytest.mark.parametrize(
    ("target", "side_effect", "error"),
    [
        pytest.param(
            GET_UNIFI_API, AuthenticationRequired, "faulty_credentials", id="auth"
        ),
        pytest.param(GET_UNIFI_API, MfaRequired, "mfa_required", id="mfa"),
        pytest.param(
            GET_UNIFI_API, CannotConnect, "service_unavailable", id="cannot_connect"
        ),
        pytest.param(
            SITES_UPDATE,
            aiounifi.RequestError,
            "service_unavailable",
            id="sites_request_error",
        ),
        pytest.param(
            SITES_UPDATE,
            aiounifi.ResponseError,
            "service_unavailable",
            id="sites_response_error",
        ),
        pytest.param(
            SITES_UPDATE, TimeoutError, "service_unavailable", id="sites_timeout"
        ),
        # Without a side effect the patched update leaves the site list empty
        pytest.param(SITES_UPDATE, None, "service_unavailable", id="sites_empty"),
        pytest.param(
            SITES_UPDATE,
            json.JSONDecodeError("", "", 0),
            "service_unavailable",
            id="sites_invalid_json",
        ),
        pytest.param(
            SITES_UPDATE,
            aiounifi.AiounifiException,
            "service_unavailable",
            id="sites_unknown_error",
        ),
        pytest.param(
            SITES_UPDATE,
            aiounifi.Forbidden,
            "faulty_credentials",
            id="sites_forbidden",
        ),
        pytest.param(
            SITES_UPDATE,
            aiounifi.LoginRequired,
            "faulty_credentials",
            id="sites_login_required",
        ),
        pytest.param(
            SITES_UPDATE,
            aiounifi.NoPermission,
            "faulty_credentials",
            id="sites_no_permission",
        ),
        pytest.param(
            SITES_UPDATE,
            aiounifi.Unauthorized,
            "faulty_credentials",
            id="sites_unauthorized",
        ),
    ],
)
@pytest.mark.usefixtures("mock_default_requests")
async def test_flow_fails_and_recovers(
    hass: HomeAssistant,
    target: str,
    side_effect: type[Exception],
    error: str,
) -> None:
    """Test config flow recovers from errors."""
    result = await _start_user_flow(hass, "full")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "full"

    with patch(target, side_effect=side_effect):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "1.2.3.4",
                CONF_USERNAME: "username",
                CONF_PASSWORD: "password",
                CONF_PORT: 1234,
                CONF_VERIFY_SSL: True,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "1.2.3.4",
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
            CONF_PORT: 1234,
            CONF_VERIFY_SSL: True,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Site name"
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
        CONF_USERNAME: "username",
        CONF_PASSWORD: "password",
        CONF_PORT: 1234,
        CONF_SITE_ID: "site_id",
        CONF_VERIFY_SSL: True,
    }
    assert result["result"].unique_id == "1"


async def test_reauth_flow_update_configuration(
    hass: HomeAssistant, config_entry_setup: MockConfigEntry
) -> None:
    """Verify reauth flow can update hub configuration."""
    config_entry = config_entry_setup

    result = await config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_full"

    context = next(
        flow["context"]
        for flow in hass.config_entries.flow.async_progress()
        if flow["flow_id"] == result["flow_id"]
    )
    assert context["title_placeholders"] == {
        "host": config_entry.data[CONF_HOST],
        "name": config_entry.title,
    }

    with patch.object(hass.config_entries, "async_schedule_reload") as mock_reload:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "1.2.3.4",
                CONF_USERNAME: "new_name",
                CONF_PASSWORD: "new_pass",
                CONF_PORT: 1234,
                CONF_VERIFY_SSL: True,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    mock_reload.assert_called_once_with(config_entry.entry_id)
    assert config_entry.data[CONF_HOST] == "1.2.3.4"
    assert config_entry.data[CONF_USERNAME] == "new_name"
    assert config_entry.data[CONF_PASSWORD] == "new_pass"


async def test_reauth_flow_reloads_not_loaded_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_requests: Callable[[str, str], None],
) -> None:
    """Verify reauth flow reloads an entry that is not loaded."""
    mock_requests(config_entry.data[CONF_HOST], config_entry.data[CONF_SITE_ID])

    result = await config_entry.start_reauth_flow(hass)

    with patch.object(hass.config_entries, "async_schedule_reload") as mock_reload:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "1.2.3.4",
                CONF_USERNAME: "new_name",
                CONF_PASSWORD: "new_pass",
                CONF_PORT: 1234,
                CONF_VERIFY_SSL: True,
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    mock_reload.assert_called_once_with(config_entry.entry_id)


async def test_reconfigure_flow_uses_update_listener_to_reload_entry(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Verify reconfigure uses the update listener to reload an entry."""
    config_entry = config_entry_setup
    config_entry._async_set_state(
        hass, config_entries.ConfigEntryState.SETUP_RETRY, "test"
    )

    try:
        result = await config_entry.start_reconfigure_flow(hass)
        result = await _select_menu(hass, result, "reconfigure_full")

        with patch.object(hass.config_entries, "async_schedule_reload") as mock_reload:
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={
                    CONF_HOST: "1.2.3.4",
                    CONF_USERNAME: "new_name",
                    CONF_PASSWORD: "new_pass",
                    CONF_PORT: 1234,
                    CONF_VERIFY_SSL: True,
                },
            )
            await hass.async_block_till_done()

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        mock_reload.assert_called_once_with(config_entry.entry_id)
        assert (
            "has an update listener and should use it for scheduling a reload"
            not in caplog.text
        )
    finally:
        config_entry._async_set_state(
            hass, config_entries.ConfigEntryState.LOADED, None
        )


async def test_reauth_flow_reloads_loaded_entry_with_unchanged_data(
    hass: HomeAssistant, config_entry_setup: MockConfigEntry
) -> None:
    """Verify reauth flow reloads a loaded entry when its data is unchanged."""
    config_entry = config_entry_setup
    data = dict(config_entry.data)

    result = await config_entry.start_reauth_flow(hass)

    with patch.object(hass.config_entries, "async_schedule_reload") as mock_reload:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: data[CONF_HOST],
                CONF_USERNAME: data[CONF_USERNAME],
                CONF_PASSWORD: data[CONF_PASSWORD],
                CONF_PORT: data[CONF_PORT],
                CONF_VERIFY_SSL: data[CONF_VERIFY_SSL],
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    mock_reload.assert_called_once_with(config_entry.entry_id)
    assert config_entry.data == data


@pytest.mark.parametrize(
    "site_payload",
    [
        [
            {"name": "site2", "role": "admin", "desc": "site2 name", "_id": "2"},
        ]
    ],
)
async def test_abort_reauth_flow_on_site_id_mismatch(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_requests: Callable[[str, str], None],
) -> None:
    """Verify reauth flow aborts when original site can no longer be found."""
    mock_requests(config_entry.data[CONF_HOST], config_entry.data[CONF_SITE_ID])

    result = await config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_full"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "1.2.3.4",
            CONF_USERNAME: "new_name",
            CONF_PASSWORD: "new_pass",
            CONF_PORT: 1234,
            CONF_VERIFY_SSL: True,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown_site_id"
    assert config_entry.data[CONF_SITE_ID] == "site_id"


async def test_reconfigure_flow_update_configuration(
    hass: HomeAssistant, config_entry_setup: MockConfigEntry
) -> None:
    """Verify reconfigure flow can update hub configuration."""
    config_entry = config_entry_setup

    result = await config_entry.start_reconfigure_flow(hass)
    result = await _select_menu(hass, result, "reconfigure_full")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_full"

    with patch.object(hass.config_entries, "async_schedule_reload") as mock_reload:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "1.2.3.4",
                CONF_USERNAME: "new_name",
                CONF_PASSWORD: "new_pass",
                CONF_PORT: 1234,
                CONF_VERIFY_SSL: True,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    mock_reload.assert_called_once_with(config_entry.entry_id)
    assert config_entry.data[CONF_HOST] == "1.2.3.4"
    assert config_entry.data[CONF_USERNAME] == "new_name"
    assert config_entry.data[CONF_PASSWORD] == "new_pass"


@pytest.mark.usefixtures("mock_default_requests")
async def test_flow_site_request_timeout(hass: HomeAssistant) -> None:
    """Test config flow gives up on a site request that does not answer."""
    result = await _start_user_flow(hass, "full")
    user_input = {
        CONF_HOST: "1.2.3.4",
        CONF_USERNAME: "username",
        CONF_PASSWORD: "password",
        CONF_PORT: 1234,
        CONF_VERIFY_SSL: True,
    }

    async def hang() -> None:
        await asyncio.Event().wait()

    with (
        patch("homeassistant.components.unifi.config_flow.SITE_REQUEST_TIMEOUT", 0),
        patch(SITES_UPDATE, side_effect=hang),
    ):
        # Fail instead of hanging if the flow does not time out
        async with asyncio.timeout(1):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input=user_input
            )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "service_unavailable"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_reconfigure_flow_with_no_sites(
    hass: HomeAssistant, config_entry_setup: MockConfigEntry
) -> None:
    """Verify an empty site list is an error that can be retried, not an abort."""
    result = await config_entry_setup.start_reconfigure_flow(hass)
    result = await _select_menu(hass, result, "reconfigure_full")
    user_input = {
        CONF_HOST: "1.2.3.4",
        CONF_USERNAME: "new_name",
        CONF_PASSWORD: "new_pass",
        CONF_PORT: 1234,
        CONF_VERIFY_SSL: True,
    }

    # Without a side effect the patched update leaves the site list empty
    with patch(SITES_UPDATE):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=user_input
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "service_unavailable"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (AuthenticationRequired, "faulty_credentials"),
        (CannotConnect, "service_unavailable"),
    ],
)
@pytest.mark.usefixtures("mock_default_requests")
async def test_reconfigure_flow_retains_user_input_on_error(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    side_effect: type[Exception],
    error: str,
) -> None:
    """Verify reconfigure flow can update hub configuration."""
    config_entry = config_entry_setup

    result = await config_entry.start_reconfigure_flow(hass)
    result = await _select_menu(hass, result, "reconfigure_full")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_full"
    user_input = {
        CONF_HOST: "4.3.2.1",
        CONF_USERNAME: "new_name",
        CONF_PASSWORD: "new_pass",
        CONF_PORT: 4321,
        CONF_VERIFY_SSL: True,
    }

    with patch(
        "homeassistant.components.unifi.config_flow.get_unifi_api",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=user_input,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert result["data_schema"]({CONF_PASSWORD: ""}) == {
        CONF_HOST: user_input[CONF_HOST],
        CONF_USERNAME: user_input[CONF_USERNAME],
        CONF_PASSWORD: "",
        CONF_PORT: user_input[CONF_PORT],
        CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={**user_input, CONF_HOST: "1.2.3.4", CONF_PORT: 1234},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.parametrize(
    "site_payload",
    [
        [
            {"name": "site2", "role": "admin", "desc": "site2 name", "_id": "2"},
        ]
    ],
)
async def test_abort_reconfigure_flow_on_site_id_mismatch(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_requests: Callable[[str, str], None],
) -> None:
    """Verify reconfigure flow aborts when original site can no longer be found."""
    mock_requests(config_entry.data[CONF_HOST], config_entry.data[CONF_SITE_ID])

    result = await config_entry.start_reconfigure_flow(hass)
    result = await _select_menu(hass, result, "reconfigure_full")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_full"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "1.2.3.4",
            CONF_USERNAME: "new_name",
            CONF_PASSWORD: "new_pass",
            CONF_PORT: 1234,
            CONF_VERIFY_SSL: True,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown_site_id"
    assert config_entry.data[CONF_SITE_ID] == "site_id"


@pytest.mark.parametrize(
    "site_payload",
    [
        [
            {
                "name": "site_id",
                "role": "admin",
                "desc": "site name",
                "_id": NEW_SITE_ID,
            },
        ]
    ],
)
async def test_reconfigure_flow_recovers_changed_site_id(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_requests: Callable[[str, str], None],
) -> None:
    """Allow reconfiguration when UniFi Network changed the site ID."""
    hass.config_entries.async_update_entry(
        config_entry,
        unique_id=OLD_SITE_ID,
        data={**config_entry.data, CONF_VERIFY_SSL: True},
    )
    mock_requests(config_entry.data[CONF_HOST], config_entry.data[CONF_SITE_ID])

    result = await config_entry.start_reconfigure_flow(hass)
    result = await _select_menu(hass, result, "reconfigure_full")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: config_entry.data[CONF_HOST],
            CONF_USERNAME: config_entry.data[CONF_USERNAME],
            CONF_PASSWORD: config_entry.data[CONF_PASSWORD],
            CONF_PORT: config_entry.data[CONF_PORT],
            CONF_VERIFY_SSL: False,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.unique_id == NEW_SITE_ID
    assert config_entry.data[CONF_VERIFY_SSL] is False


@pytest.mark.parametrize(
    "site_payload",
    [
        [
            {
                "name": "site_id",
                "role": "admin",
                "desc": "site name",
                "_id": NEW_SITE_ID,
            },
        ]
    ],
)
async def test_reconfigure_flow_recovers_changed_site_id_loaded_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    config_entry_factory: ConfigEntryFactoryType,
) -> None:
    """Allow reconfiguration of a loaded entry after UniFi changed its site ID."""
    hass.config_entries.async_update_entry(
        config_entry,
        unique_id=OLD_SITE_ID,
        data={**config_entry.data, CONF_VERIFY_SSL: True},
    )
    await config_entry_factory()
    assert config_entry.unique_id == NEW_SITE_ID

    hass.config_entries.async_update_entry(config_entry, unique_id=OLD_SITE_ID)
    result = await config_entry.start_reconfigure_flow(hass)
    result = await _select_menu(hass, result, "reconfigure_full")

    with patch.object(hass.config_entries, "async_schedule_reload") as mock_reload:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: config_entry.data[CONF_HOST],
                CONF_USERNAME: config_entry.data[CONF_USERNAME],
                CONF_PASSWORD: config_entry.data[CONF_PASSWORD],
                CONF_PORT: config_entry.data[CONF_PORT],
                CONF_VERIFY_SSL: False,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.unique_id == NEW_SITE_ID
    assert config_entry.data[CONF_VERIFY_SSL] is False
    mock_reload.assert_called_once_with(config_entry.entry_id)


@pytest.mark.parametrize("client_payload", [CLIENTS])
@pytest.mark.parametrize("device_payload", [DEVICES])
@pytest.mark.parametrize("wlan_payload", [WLANS])
@pytest.mark.parametrize("dpi_group_payload", [DPI_GROUPS])
async def test_option_flow(
    hass: HomeAssistant, config_entry_setup: MockConfigEntry
) -> None:
    """Test config flow options."""
    config_entry = config_entry_setup

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["last_step"]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_TRACK_CLIENTS: False,
            CONF_TRACK_DEVICES: False,
            CONF_BLOCK_CLIENT: [CLIENTS[0]["mac"]],
            CONF_MORE_OPTIONS: {
                CONF_CLIENT_SOURCE: ["00:00:00:00:00:01"],
                CONF_TRACK_WIRED_CLIENTS: False,
                CONF_SSID_FILTER: ["SSID 1", "SSID 2_IOT", "SSID 3", "SSID 4"],
                CONF_DETECTION_TIME: 100,
                CONF_IGNORE_LOCAL_MAC: True,
                CONF_DPI_RESTRICTIONS: False,
                CONF_ALLOW_BANDWIDTH_SENSORS: True,
                CONF_ALLOW_UPTIME_SENSORS: True,
            },
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_CLIENT_SOURCE: ["00:00:00:00:00:01"],
        CONF_TRACK_CLIENTS: False,
        CONF_TRACK_WIRED_CLIENTS: False,
        CONF_TRACK_DEVICES: False,
        CONF_SSID_FILTER: ["SSID 1", "SSID 2_IOT", "SSID 3", "SSID 4"],
        CONF_DETECTION_TIME: 100,
        CONF_IGNORE_LOCAL_MAC: True,
        CONF_IGNORE_WIRED_BUG: False,
        CONF_DPI_RESTRICTIONS: False,
        CONF_BLOCK_CLIENT: [CLIENTS[0]["mac"]],
        CONF_ALLOW_BANDWIDTH_SENSORS: True,
        CONF_ALLOW_UPTIME_SENSORS: True,
    }


async def test_option_flow_entry_not_loaded(hass: HomeAssistant) -> None:
    """Test options flow aborts when the integration is not set up."""
    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "integration_not_setup"


async def test_discover_unifi_positive(hass: HomeAssistant) -> None:
    """Verify positive run of UniFi discovery."""
    with patch("socket.gethostbyname", return_value="192.168.1.1"):
        assert await _async_discover_unifi(hass) == "192.168.1.1"


async def test_discover_unifi_negative(hass: HomeAssistant) -> None:
    """Verify negative run of UniFi discovery."""
    with patch("socket.gethostbyname", side_effect=socket.gaierror):
        assert await _async_discover_unifi(hass) is None


INTEGRATION_DISCOVERY_INFO = {
    "source_ip": "10.0.0.1",
    "hw_addr": "e0:63:da:20:14:a9",
    "name": "Dream Machine Pro",
    "hostname": "UniFi-Dream-Machine",
    "product_name": "UDMPRO",
    "platform": "UCG-Ultra",
    "direct_connect_domain": "x.ui.direct",
}


async def test_flow_integration_discovery(hass: HomeAssistant) -> None:
    """Test we get the form with integration discovery source."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data=INTEGRATION_DISCOVERY_INFO,
    )
    result = await _select_menu(hass, result, "full")
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "full"
    assert result["errors"] == {}

    context = next(
        flow["context"]
        for flow in hass.config_entries.flow.async_progress()
        if flow["flow_id"] == result["flow_id"]
    )
    assert context["configuration_url"] == "https://x.ui.direct"


@pytest.mark.parametrize(
    ("extra_info", "expected_name"),
    [
        (
            {
                "name": "Dream Machine Pro",
                "hostname": "UniFi-Dream-Machine",
                "product_name": "UDMPRO",
            },
            "Dream Machine Pro",
        ),
        (
            {"hostname": "UniFi-Dream-Machine", "product_name": "UDMPRO"},
            "UniFi-Dream-Machine",
        ),
        ({"product_name": "UDMPRO"}, "UDMPRO"),
        ({}, "UniFi Network"),
    ],
    ids=["name", "hostname", "product_name", "fallback"],
)
async def test_flow_integration_discovery_title(
    hass: HomeAssistant, extra_info: dict[str, str], expected_name: str
) -> None:
    """Test discovery title priority: name, hostname, product_name, then fallback."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={
            "source_ip": "10.0.0.1",
            "hw_addr": "e0:63:da:20:14:a9",
            "direct_connect_domain": "x.ui.direct",
            **extra_info,
        },
    )
    context = next(
        flow["context"]
        for flow in hass.config_entries.flow.async_progress()
        if flow["flow_id"] == result["flow_id"]
    )
    assert context["title_placeholders"] == {
        "host": "10.0.0.1",
        "name": expected_name,
    }


@pytest.mark.usefixtures("config_entry")
async def test_flow_integration_discovery_aborts_if_host_already_exists(
    hass: HomeAssistant,
) -> None:
    """Test we abort if the host is already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={
            **INTEGRATION_DISCOVERY_INFO,
            "source_ip": "1.2.3.4",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("config_entry")
async def test_flow_integration_discovery_aborts_on_other_announced_address(
    hass: HomeAssistant,
) -> None:
    """Test we abort when the entry uses another interface of the same console."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={
            **INTEGRATION_DISCOVERY_INFO,
            "source_ip": "10.0.0.1",
            "direct_connect_domain": None,
            "announced_ips": ["10.0.0.1", "1.2.3.4"],
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("device_payload", "client_payload", "expected_type", "expected_reason"),
    [
        pytest.param(
            [
                {
                    "board_rev": 3,
                    "device_id": "console-id",
                    "ip": "192.168.0.1",
                    "last_seen": 0,
                    "mac": INTEGRATION_DISCOVERY_INFO["hw_addr"],
                    "model": "UDMPROMAX",
                    "name": "Dream Machine Pro Max",
                    "state": 1,
                    "type": "udm",
                    "version": "5.0.16",
                }
            ],
            [],
            FlowResultType.ABORT,
            "already_configured",
            id="managed_console",
        ),
        pytest.param(
            [],
            [
                {
                    "hostname": "cloudkey",
                    "is_wired": True,
                    "last_seen": 0,
                    "mac": INTEGRATION_DISCOVERY_INFO["hw_addr"],
                    "oui": "Ubiquiti",
                    "wired_rate_mbps": 1000,
                }
            ],
            FlowResultType.MENU,
            None,
            id="console_as_client",
        ),
        pytest.param(
            [{**DEVICES[0], "mac": "e0:63:da:00:00:01"}],
            [],
            FlowResultType.MENU,
            None,
            id="other_device_same_oui",
        ),
    ],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_flow_integration_discovery_matches_managed_console(
    hass: HomeAssistant, expected_type: FlowResultType, expected_reason: str | None
) -> None:
    """Test discovery matches a managed console but not clients or other devices."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={
            **INTEGRATION_DISCOVERY_INFO,
            "source_ip": "192.168.80.1",
            "announced_ips": [],
        },
    )
    assert result["type"] is expected_type
    assert result.get("reason") == expected_reason


async def test_flow_integration_discovery_ignores_entry_without_host(
    hass: HomeAssistant,
) -> None:
    """Test an entry carrying no host does not match a missing direct connect."""
    MockConfigEntry(domain=DOMAIN, unique_id="site-id", data={}).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={**INTEGRATION_DISCOVERY_INFO, "direct_connect_domain": None},
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"


async def test_flow_integration_discovery_uses_direct_connect_domain(
    hass: HomeAssistant,
) -> None:
    """Test discovery prefers direct_connect_domain over source_ip."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data=INTEGRATION_DISCOVERY_INFO,
    )
    result = await _select_menu(hass, result, "full")
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "full"

    schema_defaults = {
        marker.schema: marker.default()
        for marker in result["data_schema"].schema
        if hasattr(marker, "default") and callable(marker.default)
    }
    assert schema_defaults[CONF_HOST] == "x.ui.direct"
    assert schema_defaults[CONF_VERIFY_SSL] is True


@pytest.mark.usefixtures("config_entry")
async def test_flow_integration_discovery_aborts_on_direct_connect_host(
    hass: HomeAssistant,
) -> None:
    """Test we abort if the direct connect domain matches a configured host."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={
            **INTEGRATION_DISCOVERY_INFO,
            "source_ip": "10.0.0.1",
            "direct_connect_domain": "1.2.3.4",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("entry_host", "extra_info"),
    [
        pytest.param("old.host", {}, id="stale_host"),
        pytest.param(
            "10.0.0.99",
            {"announced_ips": ["10.0.0.99"]},
            id="other_announced_interface",
        ),
    ],
)
async def test_flow_integration_discovery_updates_existing_entry_on_rediscovery(
    hass: HomeAssistant,
    entry_host: str,
    extra_info: dict[str, Any],
) -> None:
    """Test existing entry's host is refreshed when rediscovered with same MAC.

    This also holds when the entry sits on another interface the console
    announces, which the host match must not abort on first.
    """
    old_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=format_mac(INTEGRATION_DISCOVERY_INFO["hw_addr"]),
        data={
            CONF_HOST: entry_host,
            CONF_VERIFY_SSL: False,
        },
    )
    old_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={**INTEGRATION_DISCOVERY_INFO, **extra_info},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert old_entry.data[CONF_HOST] == "x.ui.direct"
    assert old_entry.data[CONF_VERIFY_SSL] is True


async def test_flow_integration_discovery_aborts_without_source_ip(
    hass: HomeAssistant,
) -> None:
    """Test we abort discovery when source_ip is missing."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={
            **INTEGRATION_DISCOVERY_INFO,
            "source_ip": None,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_flow_integration_discovery_gets_form_with_ignored_entry(
    hass: HomeAssistant,
) -> None:
    """Test we can still set up if there is an ignored never configured entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"not_controller_key": None},
        source=config_entries.SOURCE_IGNORE,
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data=INTEGRATION_DISCOVERY_INFO,
    )
    result = await _select_menu(hass, result, "full")
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "full"
    assert result["errors"] == {}
    context = next(
        flow["context"]
        for flow in hass.config_entries.flow.async_progress()
        if flow["flow_id"] == result["flow_id"]
    )
    assert context["title_placeholders"] == {
        "host": "10.0.0.1",
        "name": "Dream Machine Pro",
    }


API_KEY_INPUT = {
    CONF_HOST: DEFAULT_HOST,
    CONF_API_KEY: NETWORK_API_KEY,
    CONF_PORT: DEFAULT_PORT,
    CONF_VERIFY_SSL: False,
}
API_KEY_ENTRY_DATA = {
    **API_KEY_INPUT,
    CONF_SITE_ID: DEFAULT_SITE,
    CONF_CONNECTION_MODE: CONNECTION_MODE_API_KEY_ONLY,
}
SITE_OBJECT_ID = "5ba29dd4e3c58f026e9d7c38"
OBJECT_ID_SITE_PAYLOAD = [
    {"desc": "Site name", "name": DEFAULT_SITE, "role": "admin", "_id": SITE_OBJECT_ID}
]


LOCAL_USER_INPUT = {
    CONF_HOST: DEFAULT_HOST,
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
    CONF_PORT: DEFAULT_PORT,
    CONF_VERIFY_SSL: False,
}


async def test_api_key_flow(
    hass: HomeAssistant, mock_network_requests: Callable[[], None]
) -> None:
    """Test setting up an entry with only an API key."""
    mock_network_requests()

    result = await _start_user_flow(hass, "api_key")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "api_key"
    assert result["data_schema"]({CONF_API_KEY: "key"}) == {
        CONF_HOST: "unifi",
        CONF_API_KEY: "key",
        CONF_PORT: 443,
        CONF_VERIFY_SSL: False,
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=API_KEY_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Site name"
    assert result["data"] == API_KEY_ENTRY_DATA
    assert result["result"].unique_id == NETWORK_SITE_ID


@pytest.mark.parametrize(
    ("info_status", "sites_status", "sites_payload", "error"),
    [
        pytest.param(401, 200, None, "faulty_credentials", id="rejected_key"),
        pytest.param(
            404, 200, None, "network_api_unavailable", id="no_integration_api"
        ),
        pytest.param(503, 200, None, "service_unavailable", id="unavailable"),
        pytest.param(200, 403, None, "faulty_credentials", id="sites_forbidden"),
        pytest.param(200, 200, network_page([]), "service_unavailable", id="no_sites"),
    ],
)
async def test_api_key_flow_fails_and_recovers(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_network_requests: Callable[[], None],
    info_status: int,
    sites_status: int,
    sites_payload: dict[str, Any] | None,
    error: str,
) -> None:
    """Test setting up with an API key recovers from errors."""
    result = await _start_user_flow(hass, "api_key")

    aioclient_mock.get(
        f"{NETWORK_URL}/info", status=info_status, json={"applicationVersion": "10"}
    )
    aioclient_mock.get(f"{NETWORK_URL}/sites", status=sites_status, json=sites_payload)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=API_KEY_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    aioclient_mock.clear_requests()
    mock_network_requests()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=API_KEY_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == API_KEY_ENTRY_DATA


@pytest.mark.parametrize(
    ("unique_id", "expected_type"),
    [
        pytest.param(SITE_OBJECT_ID, FlowResultType.ABORT, id="same_site"),
        pytest.param("1", FlowResultType.CREATE_ENTRY, id="other_site"),
    ],
)
async def test_api_key_flow_site_of_local_user_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_network_requests: Callable[[], None],
    unique_id: str,
    expected_type: FlowResultType,
) -> None:
    """Test only a local user entry keying the same site by ObjectId aborts.

    An entry of another console at the same address can have a site of the
    same name.
    """
    hass.config_entries.async_update_entry(config_entry, unique_id=unique_id)
    mock_network_requests()
    result = await _start_user_flow(hass, "api_key")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=API_KEY_INPUT
    )

    assert result["type"] is expected_type


async def test_reauth_api_key(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_network_requests: Callable[[], None],
    network_config_entry_setup: MockConfigEntry,
) -> None:
    """Test reauth of an API key entry asks for a new key only."""
    result = await network_config_entry_setup.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_api_key"
    assert [str(marker) for marker in result["data_schema"].schema] == [CONF_API_KEY]

    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{NETWORK_URL}/info", status=401)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "wrong_key"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "faulty_credentials"}

    aioclient_mock.clear_requests()
    mock_network_requests()
    with patch.object(hass.config_entries, "async_schedule_reload") as mock_reload:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_API_KEY: "new_key"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    # The update listener reloads the loaded entry, once
    mock_reload.assert_called_once_with(network_config_entry_setup.entry_id)
    assert network_config_entry_setup.data == {
        **API_KEY_ENTRY_DATA,
        CONF_API_KEY: "new_key",
    }


@pytest.mark.parametrize("site_payload", [OBJECT_ID_SITE_PAYLOAD])
async def test_reconfigure_to_api_key(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    config_entry_factory: ConfigEntryFactoryType,
    mock_network_requests: Callable[[], None],
) -> None:
    """Test switching to an API key keeps the local user for switching back."""
    hass.config_entries.async_update_entry(config_entry, unique_id=SITE_OBJECT_ID)
    await config_entry_factory()
    mock_network_requests()
    result = await config_entry.start_reconfigure_flow(hass)
    result = await _select_menu(hass, result, "reconfigure_api_key")

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_api_key"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=API_KEY_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data == {
        **API_KEY_ENTRY_DATA,
        CONF_USERNAME: "username",
        CONF_PASSWORD: "password",
    }
    # The Integration API keys the site of an older console by UUID
    assert config_entry.unique_id == NETWORK_SITE_ID
    assert config_entry.state is ConfigEntryState.LOADED
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, NETWORK_SITE_ID), config_entry.entry_id
    )
    assert not device_registry.async_get_device_by_identifier(
        (DOMAIN, SITE_OBJECT_ID), config_entry.entry_id
    )


@pytest.mark.parametrize("site_payload", [OBJECT_ID_SITE_PAYLOAD])
async def test_reconfigure_to_local_user(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    network_config_entry_setup: MockConfigEntry,
    mock_requests: Callable[[str, str], None],
) -> None:
    """Test switching to a local user keeps the API key for switching back."""
    mock_requests(DEFAULT_HOST, DEFAULT_SITE)
    result = await network_config_entry_setup.start_reconfigure_flow(hass)
    result = await _select_menu(hass, result, "reconfigure_full")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=LOCAL_USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert network_config_entry_setup.data == {
        **LOCAL_USER_INPUT,
        CONF_API_KEY: NETWORK_API_KEY,
        CONF_SITE_ID: DEFAULT_SITE,
    }
    assert network_config_entry_setup.unique_id == SITE_OBJECT_ID
    assert network_config_entry_setup.state is ConfigEntryState.LOADED
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, SITE_OBJECT_ID), network_config_entry_setup.entry_id
    )
    assert not device_registry.async_get_device_by_identifier(
        (DOMAIN, NETWORK_SITE_ID), network_config_entry_setup.entry_id
    )


@pytest.mark.parametrize("site_payload", [OBJECT_ID_SITE_PAYLOAD])
async def test_reconfigure_mode_on_other_console(
    hass: HomeAssistant,
    network_config_entry_setup: MockConfigEntry,
    mock_requests: Callable[[str, str], None],
) -> None:
    """Test a site of the same name on another console is not taken over."""
    mock_requests("5.6.7.8", DEFAULT_SITE)
    result = await network_config_entry_setup.start_reconfigure_flow(hass)
    result = await _select_menu(hass, result, "reconfigure_full")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={**LOCAL_USER_INPUT, CONF_HOST: "5.6.7.8"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown_site_id"
    assert network_config_entry_setup.unique_id == NETWORK_SITE_ID


@pytest.mark.parametrize("site_payload", [OBJECT_ID_SITE_PAYLOAD])
async def test_reconfigure_mode_to_configured_site(
    hass: HomeAssistant,
    network_config_entry_setup: MockConfigEntry,
    mock_requests: Callable[[str, str], None],
) -> None:
    """Test the site an other entry has is not taken over."""
    MockConfigEntry(domain=DOMAIN, unique_id=SITE_OBJECT_ID).add_to_hass(hass)
    mock_requests(DEFAULT_HOST, DEFAULT_SITE)
    result = await network_config_entry_setup.start_reconfigure_flow(hass)
    result = await _select_menu(hass, result, "reconfigure_full")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=LOCAL_USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert network_config_entry_setup.unique_id == NETWORK_SITE_ID


async def test_reconfigure_api_key_keeps_stored_key(
    hass: HomeAssistant,
    network_config_entry_setup: MockConfigEntry,
    mock_network_requests: Callable[[], None],
) -> None:
    """Test an empty API key keeps the stored one."""
    mock_network_requests()
    result = await network_config_entry_setup.start_reconfigure_flow(hass)
    result = await _select_menu(hass, result, "reconfigure_api_key")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            key: value for key, value in API_KEY_INPUT.items() if key != CONF_API_KEY
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert network_config_entry_setup.data == API_KEY_ENTRY_DATA


async def test_reconfigure_api_key_unknown_site(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    network_config_entry_setup: MockConfigEntry,
) -> None:
    """Test reconfigure aborts when the site of the entry is gone."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{NETWORK_URL}/info", json={"applicationVersion": "10"})
    aioclient_mock.get(
        f"{NETWORK_URL}/sites",
        json=network_page(
            [{"id": "other-site", "internalReference": "other", "name": "Other"}]
        ),
    )
    result = await network_config_entry_setup.start_reconfigure_flow(hass)
    result = await _select_menu(hass, result, "reconfigure_api_key")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=API_KEY_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown_site_id"
    assert network_config_entry_setup.unique_id == NETWORK_SITE_ID


async def test_api_key_flow_multiple_sites(
    hass: HomeAssistant,
    mock_network_requests: Callable[[], None],
    network_site_payload: list[dict[str, Any]],
) -> None:
    """Test an API key that sees several sites asks which one to set up."""
    network_site_payload.append(
        {"id": "other-site", "internalReference": "other", "name": "Other"}
    )
    mock_network_requests()
    result = await _start_user_flow(hass, "api_key")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=API_KEY_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "site"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_SITE_ID: "other-site"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Other"
    assert result["data"] == {**API_KEY_ENTRY_DATA, CONF_SITE_ID: "other"}
    assert result["result"].unique_id == "other-site"


async def test_flow_integration_discovery_matches_api_key_console(
    hass: HomeAssistant,
    network_device_payload: list[dict[str, Any]],
    network_config_entry_factory: ConfigEntryFactoryType,
) -> None:
    """Test discovery finds a console that an API key entry lists."""
    network_device_payload.append(
        {
            "id": "4ff3bc5f-6d39-3d2e-9bfd-0f2bf6c3f1d4",
            "macAddress": INTEGRATION_DISCOVERY_INFO["hw_addr"],
            "model": "UDM Pro",
            "name": "Console",
            "state": "ONLINE",
            "supported": True,
        }
    )
    await network_config_entry_factory()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={
            **INTEGRATION_DISCOVERY_INFO,
            "source_ip": "192.168.80.1",
            "direct_connect_domain": None,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
