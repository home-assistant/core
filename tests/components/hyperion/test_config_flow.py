"""Tests for the Hyperion config flow."""

import logging
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, patch

from hyperion import const

from homeassistant import data_entry_flow
from homeassistant.components.hyperion.const import (
    CONF_AUTH_ID,
    CONF_CREATE_TOKEN,
    CONF_PRIORITY,
    DOMAIN,
)
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_SSDP, SOURCE_USER
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_PORT,
    CONF_TOKEN,
    SERVICE_TURN_ON,
)
from homeassistant.helpers.typing import HomeAssistantType

from . import (
    TEST_AUTH_REQUIRED_RESP,
    TEST_CONFIG_ENTRY_ID,
    TEST_ENTITY_ID_1,
    TEST_HOST,
    TEST_INSTANCE,
    TEST_PORT,
    TEST_PORT_UI,
    TEST_SYSINFO_ID,
    TEST_TITLE,
    TEST_TOKEN,
    add_test_config_entry,
    create_mock_client,
)

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)

TEST_IP_ADDRESS = "192.168.0.1"
TEST_HOST_PORT: Dict[str, Any] = {
    CONF_HOST: TEST_HOST,
    CONF_PORT: TEST_PORT,
}

TEST_AUTH_ID = "ABCDE"
TEST_REQUEST_TOKEN_SUCCESS = {
    "command": "authorize-requestToken",
    "success": True,
    "info": {"comment": const.DEFAULT_ORIGIN, "id": TEST_AUTH_ID, "token": TEST_TOKEN},
}

TEST_REQUEST_TOKEN_FAIL = {
    "command": "authorize-requestToken",
    "success": False,
    "error": "Token request timeout or denied",
}

TEST_SSDP_SERVICE_INFO = {
    "ssdp_location": f"http://{TEST_HOST}:{TEST_PORT_UI}/description.xml",
    "ssdp_st": "upnp:rootdevice",
    "deviceType": "urn:schemas-upnp-org:device:Basic:1",
    "friendlyName": f"Hyperion ({TEST_HOST})",
    "manufacturer": "Hyperion Open Source Ambient Lighting",
    "manufacturerURL": "https://www.hyperion-project.org",
    "modelDescription": "Hyperion Open Source Ambient Light",
    "modelName": "Hyperion",
    "modelNumber": "2.0.0-alpha.8",
    "modelURL": "https://www.hyperion-project.org",
    "serialNumber": f"{TEST_SYSINFO_ID}",
    "UDN": f"uuid:{TEST_SYSINFO_ID}",
    "ports": {
        "jsonServer": f"{TEST_PORT}",
        "sslServer": "8092",
        "protoBuffer": "19445",
        "flatBuffer": "19400",
    },
    "presentationURL": "index.html",
    "iconList": {
        "icon": {
            "mimetype": "image/png",
            "height": "100",
            "width": "100",
            "depth": "32",
            "url": "img/hyperion/ssdp_icon.png",
        }
    },
    "ssdp_usn": f"uuid:{TEST_SYSINFO_ID}",
    "ssdp_ext": "",
    "ssdp_server": "Raspbian GNU/Linux 10 (buster)/10 UPnP/1.0 Hyperion/2.0.0-alpha.8",
}


async def _create_mock_entry(hass: HomeAssistantType) -> MockConfigEntry:
    """Add a test Hyperion entity to hass."""
    entry: MockConfigEntry = MockConfigEntry(  # type: ignore[no-untyped-call]
        entry_id=TEST_CONFIG_ENTRY_ID,
        domain=DOMAIN,
        unique_id=TEST_SYSINFO_ID,
        title=TEST_TITLE,
        data={
            "host": TEST_HOST,
            "port": TEST_PORT,
            "instance": TEST_INSTANCE,
        },
    )
    entry.add_to_hass(hass)  # type: ignore[no-untyped-call]

    # Setup
    client = create_mock_client()
    with patch(
        "homeassistant.components.hyperion.client.HyperionClient", return_value=client
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


async def _init_flow(
    hass: HomeAssistantType,
    source: str = SOURCE_USER,
    data: Optional[Dict[str, Any]] = None,
) -> Any:
    """Initialize a flow."""
    data = data or {}

    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": source}, data=data
    )


async def _configure_flow(
    hass: HomeAssistantType, result: Dict, user_input: Optional[Dict[str, Any]] = None
) -> Any:
    """Provide input to a flow."""
    user_input = user_input or {}

    with patch(
        "homeassistant.components.hyperion.async_setup", return_value=True
    ), patch(
        "homeassistant.components.hyperion.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=user_input
        )
        await hass.async_block_till_done()
    return result


async def test_user_if_no_configuration(hass: HomeAssistantType) -> None:
    """Check flow behavior when no configuration is present."""
    result = await _init_flow(hass)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["handler"] == DOMAIN


async def test_user_existing_id_abort(hass: HomeAssistantType) -> None:
    """Verify a duplicate ID results in an abort."""
    result = await _init_flow(hass)

    await _create_mock_entry(hass)
    client = create_mock_client()
    with patch(
        "homeassistant.components.hyperion.client.HyperionClient", return_value=client
    ):
        result = await _configure_flow(hass, result, user_input=TEST_HOST_PORT)
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"


async def test_user_client_errors(hass: HomeAssistantType) -> None:
    """Verify correct behaviour with client errors."""
    result = await _init_flow(hass)

    client = create_mock_client()

    # Fail the connection.
    client.async_client_connect = AsyncMock(return_value=False)
    with patch(
        "homeassistant.components.hyperion.client.HyperionClient", return_value=client
    ):
        result = await _configure_flow(hass, result, user_input=TEST_HOST_PORT)
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"]["base"] == "cannot_connect"

    # Fail the auth check call.
    client.async_client_connect = AsyncMock(return_value=True)
    client.async_is_auth_required = AsyncMock(return_value={"success": False})
    with patch(
        "homeassistant.components.hyperion.client.HyperionClient", return_value=client
    ):
        result = await _configure_flow(hass, result, user_input=TEST_HOST_PORT)
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "auth_required_error"


async def test_user_confirm_cannot_connect(hass: HomeAssistantType) -> None:
    """Test a failure to connect during confirmation."""

    result = await _init_flow(hass)

    good_client = create_mock_client()
    bad_client = create_mock_client()
    bad_client.async_client_connect = AsyncMock(return_value=False)

    # Confirmation sync_client_connect fails.
    with patch(
        "homeassistant.components.hyperion.client.HyperionClient",
        side_effect=[good_client, bad_client],
    ):
        result = await _configure_flow(hass, result, user_input=TEST_HOST_PORT)
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "cannot_connect"


async def test_user_confirm_id_error(hass: HomeAssistantType) -> None:
    """Test a failure fetching the server id during confirmation."""
    result = await _init_flow(hass)

    client = create_mock_client()
    client.async_sysinfo_id = AsyncMock(return_value=None)

    # Confirmation sync_client_connect fails.
    with patch(
        "homeassistant.components.hyperion.client.HyperionClient", return_value=client
    ):
        result = await _configure_flow(hass, result, user_input=TEST_HOST_PORT)
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "no_id"


async def test_user_noauth_flow_success(hass: HomeAssistantType) -> None:
    """Check a full flow without auth."""
    result = await _init_flow(hass)

    client = create_mock_client()
    with patch(
        "homeassistant.components.hyperion.client.HyperionClient", return_value=client
    ):
        result = await _configure_flow(hass, result, user_input=TEST_HOST_PORT)

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["handler"] == DOMAIN
    assert result["title"] == TEST_TITLE
    assert result["data"] == {
        **TEST_HOST_PORT,
    }


async def test_user_auth_required(hass: HomeAssistantType) -> None:
    """Verify correct behaviour when auth is required."""
    result = await _init_flow(hass)

    client = create_mock_client()
    client.async_is_auth_required = AsyncMock(return_value=TEST_AUTH_REQUIRED_RESP)

    with patch(
        "homeassistant.components.hyperion.client.HyperionClient", return_value=client
    ):
        result = await _configure_flow(hass, result, user_input=TEST_HOST_PORT)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "auth"


async def test_auth_static_token_auth_required_fail(hass: HomeAssistantType) -> None:
    """Verify correct behaviour with a failed auth required call."""
    result = await _init_flow(hass)

    client = create_mock_client()
    client.async_is_auth_required = AsyncMock(return_value=None)
    with patch(
        "homeassistant.components.hyperion.client.HyperionClient", return_value=client
    ):
        result = await _configure_flow(hass, result, user_input=TEST_HOST_PORT)
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "auth_required_error"


async def test_auth_static_token_success(hass: HomeAssistantType) -> None:
    """Test a successful flow with a static token."""
    result = await _init_flow(hass)
    assert result["step_id"] == "user"

    client = create_mock_client()
    client.async_is_auth_required = AsyncMock(return_value=TEST_AUTH_REQUIRED_RESP)

    with patch(
        "homeassistant.components.hyperion.client.HyperionClient", return_value=client
    ):
        result = await _configure_flow(hass, result, user_input=TEST_HOST_PORT)
        result = await _configure_flow(
            hass, result, user_input={CONF_CREATE_TOKEN: False, CONF_TOKEN: TEST_TOKEN}
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["handler"] == DOMAIN
    assert result["title"] == TEST_TITLE
    assert result["data"] == {
        **TEST_HOST_PORT,
        CONF_TOKEN: TEST_TOKEN,
    }


async def test_auth_static_token_login_fail(hass: HomeAssistantType) -> None:
    """Test correct behavior with a bad static token."""
    result = await _init_flow(hass)
    assert result["step_id"] == "user"

    client = create_mock_client()
    client.async_is_auth_required = AsyncMock(return_value=TEST_AUTH_REQUIRED_RESP)

    # Fail the login call.
    client.async_login = AsyncMock(
        return_value={"command": "authorize-login", "success": False, "tan": 0}
    )

    with patch(
        "homeassistant.components.hyperion.client.HyperionClient", return_value=client
    ):
        result = await _configure_flow(hass, result, user_input=TEST_HOST_PORT)
        result = await _configure_flow(
            hass, result, user_input={CONF_CREATE_TOKEN: False, CONF_TOKEN: TEST_TOKEN}
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"]["base"] == "invalid_access_token"


async def test_auth_create_token_approval_declined(hass: HomeAssistantType) -> None:
    """Verify correct behaviour when a token request is declined."""
    result = await _init_flow(hass)

    client = create_mock_client()
    client.async_is_auth_required = AsyncMock(return_value=TEST_AUTH_REQUIRED_RESP)

    with patch(
        "homeassistant.components.hyperion.client.HyperionClient", return_value=client
    ):
        result = await _configure_flow(hass, result, user_input=TEST_HOST_PORT)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "auth"

    client.async_request_token = AsyncMock(return_value=TEST_REQUEST_TOKEN_FAIL)
    with patch(
        "homeassistant.components.hyperion.client.HyperionClient", return_value=client
    ), patch(
        "homeassistant.components.hyperion.config_flow.client.generate_random_auth_id",
        return_value=TEST_AUTH_ID,
    ):
        result = await _configure_flow(
            hass, result, user_input={CONF_CREATE_TOKEN: True}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "create_token"
        assert result["description_placeholders"] == {
            CONF_AUTH_ID: TEST_AUTH_ID,
        }

        result = await _configure_flow(hass, result)
        await hass.async_block_till_done()
        assert result["type"] == data_entry_flow.RESULT_TYPE_EXTERNAL_STEP
        assert result["step_id"] == "create_token_external"

        # The flow will be automatically advanced by the auth token response.

        result = await _configure_flow(hass, result)
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "auth_new_token_not_granted_error"


async def test_auth_create_token_when_issued_token_fails(
    hass: HomeAssistantType,
) -> None:
    """Verify correct behaviour when a token is granted by fails to authenticate."""
    result = await _init_flow(hass)

    client = create_mock_client()
    client.async_is_auth_required = AsyncMock(return_value=TEST_AUTH_REQUIRED_RESP)

    with patch(
        "homeassistant.components.hyperion.client.HyperionClient", return_value=client
    ):
        result = await _configure_flow(hass, result, user_input=TEST_HOST_PORT)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "auth"

    client.async_request_token = AsyncMock(return_value=TEST_REQUEST_TOKEN_SUCCESS)
    with patch(
        "homeassistant.components.hyperion.client.HyperionClient", return_value=client
    ), patch(
        "homeassistant.components.hyperion.config_flow.client.generate_random_auth_id",
        return_value=TEST_AUTH_ID,
    ):
        result = await _configure_flow(
            hass, result, user_input={CONF_CREATE_TOKEN: True}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "create_token"
        assert result["description_placeholders"] == {
            CONF_AUTH_ID: TEST_AUTH_ID,
        }

        result = await _configure_flow(hass, result)
        assert result["type"] == data_entry_flow.RESULT_TYPE_EXTERNAL_STEP
        assert result["step_id"] == "create_token_external"

        # The flow will be automatically advanced by the auth token response.

        # Make the last verification fail.
        client.async_client_connect = AsyncMock(return_value=False)

        result = await _configure_flow(hass, result)
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "cannot_connect"


async def test_auth_create_token_success(hass: HomeAssistantType) -> None:
    """Verify correct behaviour when a token is successfully created."""
    result = await _init_flow(hass)

    client = create_mock_client()
    client.async_is_auth_required = AsyncMock(return_value=TEST_AUTH_REQUIRED_RESP)

    with patch(
        "homeassistant.components.hyperion.client.HyperionClient", return_value=client
    ):
        result = await _configure_flow(hass, result, user_input=TEST_HOST_PORT)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "auth"

    client.async_request_token = AsyncMock(return_value=TEST_REQUEST_TOKEN_SUCCESS)
    with patch(
        "homeassistant.components.hyperion.client.HyperionClient", return_value=client
    ), patch(
        "homeassistant.components.hyperion.config_flow.client.generate_random_auth_id",
        return_value=TEST_AUTH_ID,
    ):
        result = await _configure_flow(
            hass, result, user_input={CONF_CREATE_TOKEN: True}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "create_token"
        assert result["description_placeholders"] == {
            CONF_AUTH_ID: TEST_AUTH_ID,
        }

        result = await _configure_flow(hass, result)
        assert result["type"] == data_entry_flow.RESULT_TYPE_EXTERNAL_STEP
        assert result["step_id"] == "create_token_external"

        # The flow will be automatically advanced by the auth token response.
        result = await _configure_flow(hass, result)
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["handler"] == DOMAIN
        assert result["title"] == TEST_TITLE
        assert result["data"] == {
            **TEST_HOST_PORT,
            CONF_TOKEN: TEST_TOKEN,
        }


async def test_ssdp_success(hass: HomeAssistantType) -> None:
    """Check an SSDP flow."""

    client = create_mock_client()
    with patch(
        "homeassistant.components.hyperion.client.HyperionClient", return_value=client
    ):
        result = await _init_flow(hass, source=SOURCE_SSDP, data=TEST_SSDP_SERVICE_INFO)
        await hass.async_block_till_done()

    # Accept the confirmation.
    with patch(
        "homeassistant.components.hyperion.client.HyperionClient", return_value=client
    ):
        result = await _configure_flow(hass, result)

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["handler"] == DOMAIN
    assert result["title"] == TEST_TITLE
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_PORT: TEST_PORT,
    }


async def test_ssdp_cannot_connect(hass: HomeAssistantType) -> None:
    """Check an SSDP flow that cannot connect."""

    client = create_mock_client()
    client.async_client_connect = AsyncMock(return_value=False)

    with patch(
        "homeassistant.components.hyperion.client.HyperionClient", return_value=client
    ):
        result = await _init_flow(hass, source=SOURCE_SSDP, data=TEST_SSDP_SERVICE_INFO)
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "cannot_connect"


async def test_ssdp_missing_serial(hass: HomeAssistantType) -> None:
    """Check an SSDP flow where no id is provided."""

    client = create_mock_client()
    bad_data = {**TEST_SSDP_SERVICE_INFO}
    del bad_data["serialNumber"]

    with patch(
        "homeassistant.components.hyperion.client.HyperionClient", return_value=client
    ):
        result = await _init_flow(hass, source=SOURCE_SSDP, data=bad_data)
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "no_id"


async def test_ssdp_failure_bad_port_json(hass: HomeAssistantType) -> None:
    """Check an SSDP flow with bad json port."""

    client = create_mock_client()
    bad_data: Dict[str, Any] = {**TEST_SSDP_SERVICE_INFO}
    bad_data["ports"]["jsonServer"] = "not_a_port"

    with patch(
        "homeassistant.components.hyperion.client.HyperionClient", return_value=client
    ):
        result = await _init_flow(hass, source=SOURCE_SSDP, data=bad_data)
        result = await _configure_flow(hass, result)
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["data"][CONF_PORT] == const.DEFAULT_PORT_JSON


async def test_ssdp_failure_bad_port_ui(hass: HomeAssistantType) -> None:
    """Check an SSDP flow with bad ui port."""

    client = create_mock_client()
    client.async_is_auth_required = AsyncMock(return_value=TEST_AUTH_REQUIRED_RESP)

    bad_data = {**TEST_SSDP_SERVICE_INFO}
    bad_data["ssdp_location"] = f"http://{TEST_HOST}:not_a_port/description.xml"

    with patch(
        "homeassistant.components.hyperion.client.HyperionClient", return_value=client
    ), patch(
        "homeassistant.components.hyperion.config_flow.client.generate_random_auth_id",
        return_value=TEST_AUTH_ID,
    ):
        result = await _init_flow(hass, source=SOURCE_SSDP, data=bad_data)

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"

        client.async_request_token = AsyncMock(return_value=TEST_REQUEST_TOKEN_FAIL)

        result = await _configure_flow(
            hass, result, user_input={CONF_CREATE_TOKEN: True}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "create_token"

        # Verify a working URL is used despite the bad port number
        assert result["description_placeholders"] == {
            CONF_AUTH_ID: TEST_AUTH_ID,
        }


async def test_ssdp_abort_duplicates(hass: HomeAssistantType) -> None:
    """Check an SSDP flow where no id is provided."""

    client = create_mock_client()
    with patch(
        "homeassistant.components.hyperion.client.HyperionClient", return_value=client
    ):
        result_1 = await _init_flow(
            hass, source=SOURCE_SSDP, data=TEST_SSDP_SERVICE_INFO
        )
        result_2 = await _init_flow(
            hass, source=SOURCE_SSDP, data=TEST_SSDP_SERVICE_INFO
        )
        await hass.async_block_till_done()

    assert result_1["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result_2["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result_2["reason"] == "already_in_progress"


async def test_options(hass: HomeAssistantType) -> None:
    """Check an options flow."""

    config_entry = add_test_config_entry(hass)

    client = create_mock_client()
    with patch(
        "homeassistant.components.hyperion.client.HyperionClient", return_value=client
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get(TEST_ENTITY_ID_1) is not None

        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        new_priority = 1
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_PRIORITY: new_priority}
        )
        await hass.async_block_till_done()
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["data"] == {CONF_PRIORITY: new_priority}

        # Turn the light on and ensure the new priority is used.
        client.async_send_set_color = AsyncMock(return_value=True)
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: TEST_ENTITY_ID_1},
            blocking=True,
        )
        # pylint: disable=unsubscriptable-object
        assert client.async_send_set_color.call_args[1][CONF_PRIORITY] == new_priority


async def test_reauth_success(hass: HomeAssistantType) -> None:
    """Check a reauth flow that succeeds."""

    config_data = {
        CONF_HOST: TEST_HOST,
        CONF_PORT: TEST_PORT,
    }

    config_entry = add_test_config_entry(hass, data=config_data)
    client = create_mock_client()
    client.async_is_auth_required = AsyncMock(return_value=TEST_AUTH_REQUIRED_RESP)

    with patch(
        "homeassistant.components.hyperion.client.HyperionClient", return_value=client
    ), patch("homeassistant.components.hyperion.async_setup", return_value=True), patch(
        "homeassistant.components.hyperion.async_setup_entry", return_value=True
    ):
        result = await _init_flow(
            hass,
            source=SOURCE_REAUTH,
            data=config_data,
        )
        await hass.async_block_till_done()
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        result = await _configure_flow(
            hass, result, user_input={CONF_CREATE_TOKEN: False, CONF_TOKEN: TEST_TOKEN}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "reauth_successful"
        assert CONF_TOKEN in config_entry.data


async def test_reauth_cannot_connect(hass: HomeAssistantType) -> None:
    """Check a reauth flow that fails to connect."""

    config_data = {
        CONF_HOST: TEST_HOST,
        CONF_PORT: TEST_PORT,
    }

    add_test_config_entry(hass, data=config_data)
    client = create_mock_client()
    client.async_client_connect = AsyncMock(return_value=False)

    with patch(
        "homeassistant.components.hyperion.client.HyperionClient", return_value=client
    ):
        result = await _init_flow(
            hass,
            source=SOURCE_REAUTH,
            data=config_data,
        )
        await hass.async_block_till_done()
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "cannot_connect"
