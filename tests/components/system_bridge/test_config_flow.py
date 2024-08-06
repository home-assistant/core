"""Test the System Bridge config flow."""

from unittest.mock import patch

from systembridgeconnector.exceptions import (
    AuthenticationException,
    ConnectionClosedException,
    ConnectionErrorException,
)

from homeassistant import config_entries
from homeassistant.components.system_bridge.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    FIXTURE_AUTH_INPUT,
    FIXTURE_DATA_RESPONSE,
    FIXTURE_USER_INPUT,
    FIXTURE_UUID,
    FIXTURE_ZEROCONF,
    FIXTURE_ZEROCONF_BAD,
    FIXTURE_ZEROCONF_INPUT,
    mock_data_listener,
)

from tests.common import MockConfigEntry


async def test_show_user_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_flow(hass: HomeAssistant) -> None:
    """Test full user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with (
        patch(
            "homeassistant.components.system_bridge.config_flow.WebSocketClient.connect"
        ),
        patch(
            "systembridgeconnector.websocket_client.WebSocketClient.get_data",
            return_value=FIXTURE_DATA_RESPONSE,
        ),
        patch(
            "systembridgeconnector.websocket_client.WebSocketClient.listen",
            new=mock_data_listener,
        ),
        patch(
            "homeassistant.components.system_bridge.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT
        )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "127.0.0.1"
    assert result2["data"] == FIXTURE_USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "systembridgeconnector.websocket_client.WebSocketClient.connect",
        side_effect=ConnectionErrorException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT
        )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_connection_closed_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle connection closed cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with (
        patch(
            "homeassistant.components.system_bridge.config_flow.WebSocketClient.connect"
        ),
        patch(
            "systembridgeconnector.websocket_client.WebSocketClient.get_data",
            side_effect=ConnectionClosedException,
        ),
        patch(
            "systembridgeconnector.websocket_client.WebSocketClient.listen",
            new=mock_data_listener,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT
        )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_timeout_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle timeout cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with (
        patch(
            "homeassistant.components.system_bridge.config_flow.WebSocketClient.connect"
        ),
        patch(
            "systembridgeconnector.websocket_client.WebSocketClient.get_data",
            side_effect=TimeoutError,
        ),
        patch(
            "systembridgeconnector.websocket_client.WebSocketClient.listen",
            new=mock_data_listener,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT
        )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with (
        patch(
            "homeassistant.components.system_bridge.config_flow.WebSocketClient.connect"
        ),
        patch(
            "systembridgeconnector.websocket_client.WebSocketClient.get_data",
            side_effect=AuthenticationException,
        ),
        patch(
            "systembridgeconnector.websocket_client.WebSocketClient.listen",
            new=mock_data_listener,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT
        )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_uuid_error(hass: HomeAssistant) -> None:
    """Test we handle error from bad uuid."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with (
        patch(
            "homeassistant.components.system_bridge.config_flow.WebSocketClient.connect"
        ),
        patch(
            "systembridgeconnector.websocket_client.WebSocketClient.get_data",
            side_effect=ValueError,
        ),
        patch(
            "systembridgeconnector.websocket_client.WebSocketClient.listen",
            new=mock_data_listener,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT
        )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle unknown errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with (
        patch(
            "homeassistant.components.system_bridge.config_flow.WebSocketClient.connect"
        ),
        patch(
            "systembridgeconnector.websocket_client.WebSocketClient.get_data",
            side_effect=Exception,
        ),
        patch(
            "systembridgeconnector.websocket_client.WebSocketClient.listen",
            new=mock_data_listener,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT
        )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "unknown"}


async def test_reauth_authorization_error(hass: HomeAssistant) -> None:
    """Test we show user form on authorization error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reauth"}, data=FIXTURE_USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "authenticate"

    with (
        patch(
            "homeassistant.components.system_bridge.config_flow.WebSocketClient.connect"
        ),
        patch(
            "systembridgeconnector.websocket_client.WebSocketClient.get_data",
            side_effect=AuthenticationException,
        ),
        patch(
            "systembridgeconnector.websocket_client.WebSocketClient.listen",
            new=mock_data_listener,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_AUTH_INPUT
        )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "authenticate"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_reauth_connection_error(hass: HomeAssistant) -> None:
    """Test we show user form on connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reauth"}, data=FIXTURE_USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "authenticate"

    with patch(
        "systembridgeconnector.websocket_client.WebSocketClient.connect",
        side_effect=ConnectionErrorException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_AUTH_INPUT
        )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "authenticate"
    assert result2["errors"] == {"base": "cannot_connect"}

    with (
        patch(
            "systembridgeconnector.websocket_client.WebSocketClient.connect",
        ),
        patch(
            "systembridgeconnector.websocket_client.WebSocketClient.get_data",
            return_value=None,
        ),
        patch(
            "systembridgeconnector.websocket_client.WebSocketClient.listen",
            new=mock_data_listener,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_AUTH_INPUT
        )
    await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "authenticate"
    assert result3["errors"] == {"base": "cannot_connect"}


async def test_reauth_connection_closed_error(hass: HomeAssistant) -> None:
    """Test we show user form on connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reauth"}, data=FIXTURE_USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "authenticate"

    with (
        patch(
            "homeassistant.components.system_bridge.config_flow.WebSocketClient.connect"
        ),
        patch(
            "systembridgeconnector.websocket_client.WebSocketClient.get_data",
            side_effect=ConnectionClosedException,
        ),
        patch(
            "systembridgeconnector.websocket_client.WebSocketClient.listen",
            new=mock_data_listener,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_AUTH_INPUT
        )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "authenticate"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_reauth_flow(hass: HomeAssistant) -> None:
    """Test reauth flow."""
    mock_config = MockConfigEntry(
        domain=DOMAIN, unique_id=FIXTURE_UUID, data=FIXTURE_USER_INPUT
    )
    mock_config.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reauth"}, data=FIXTURE_USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "authenticate"

    with (
        patch(
            "homeassistant.components.system_bridge.config_flow.WebSocketClient.connect"
        ),
        patch(
            "systembridgeconnector.websocket_client.WebSocketClient.get_data",
            return_value=FIXTURE_DATA_RESPONSE,
        ),
        patch(
            "systembridgeconnector.websocket_client.WebSocketClient.listen",
            new=mock_data_listener,
        ),
        patch(
            "homeassistant.components.system_bridge.async_setup_entry",
            return_value=True,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_AUTH_INPUT
        )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"


async def test_zeroconf_flow(hass: HomeAssistant) -> None:
    """Test zeroconf flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=FIXTURE_ZEROCONF,
    )

    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    with (
        patch(
            "homeassistant.components.system_bridge.config_flow.WebSocketClient.connect"
        ),
        patch(
            "systembridgeconnector.websocket_client.WebSocketClient.get_data",
            return_value=FIXTURE_DATA_RESPONSE,
        ),
        patch(
            "systembridgeconnector.websocket_client.WebSocketClient.listen",
            new=mock_data_listener,
        ),
        patch(
            "homeassistant.components.system_bridge.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_AUTH_INPUT
        )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "127.0.0.1"
    assert result2["data"] == FIXTURE_ZEROCONF_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_cannot_connect(hass: HomeAssistant) -> None:
    """Test zeroconf cannot connect flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=FIXTURE_ZEROCONF,
    )

    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    with patch(
        "systembridgeconnector.websocket_client.WebSocketClient.connect",
        side_effect=ConnectionErrorException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_AUTH_INPUT
        )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "authenticate"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_zeroconf_bad_zeroconf_info(hass: HomeAssistant) -> None:
    """Test zeroconf cannot connect flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=FIXTURE_ZEROCONF_BAD,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"
