"""Test the System Bridge config flow."""
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from ipaddress import ip_address
from typing import Any
from unittest.mock import patch

from systembridgeconnector.const import TYPE_DATA_UPDATE
from systembridgeconnector.exceptions import (
    AuthenticationException,
    ConnectionClosedException,
    ConnectionErrorException,
)
from systembridgemodels.const import MODEL_SYSTEM
from systembridgemodels.modules.system import System
from systembridgemodels.response import Response

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import zeroconf
from homeassistant.components.system_bridge.config_flow import SystemBridgeConfigFlow
from homeassistant.components.system_bridge.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

FIXTURE_MAC_ADDRESS = "aa:bb:cc:dd:ee:ff"
FIXTURE_UUID = "e91bf575-56f3-4c83-8f42-70ac17adcd33"

FIXTURE_AUTH_INPUT = {CONF_TOKEN: "abc-123-def-456-ghi"}

FIXTURE_USER_INPUT = {
    CONF_TOKEN: "abc-123-def-456-ghi",
    CONF_HOST: "test-bridge",
    CONF_PORT: "9170",
}

FIXTURE_ZEROCONF_INPUT = {
    CONF_TOKEN: "abc-123-def-456-ghi",
    CONF_HOST: "1.1.1.1",
    CONF_PORT: "9170",
}

FIXTURE_ZEROCONF = zeroconf.ZeroconfServiceInfo(
    ip_address=ip_address("1.1.1.1"),
    ip_addresses=[ip_address("1.1.1.1")],
    port=9170,
    hostname="test-bridge.local.",
    type="_system-bridge._tcp.local.",
    name="System Bridge - test-bridge._system-bridge._tcp.local.",
    properties={
        "address": "http://test-bridge:9170",
        "fqdn": "test-bridge",
        "host": "test-bridge",
        "ip": "1.1.1.1",
        "mac": FIXTURE_MAC_ADDRESS,
        "port": "9170",
        "uuid": FIXTURE_UUID,
    },
)

FIXTURE_ZEROCONF_BAD = zeroconf.ZeroconfServiceInfo(
    ip_address=ip_address("1.1.1.1"),
    ip_addresses=[ip_address("1.1.1.1")],
    port=9170,
    hostname="test-bridge.local.",
    type="_system-bridge._tcp.local.",
    name="System Bridge - test-bridge._system-bridge._tcp.local.",
    properties={
        "something": "bad",
    },
)


FIXTURE_SYSTEM = System(
    boot_time=1,
    fqdn="",
    hostname="1.1.1.1",
    ip_address_4="1.1.1.1",
    mac_address=FIXTURE_MAC_ADDRESS,
    platform="",
    platform_version="",
    uptime=1,
    uuid=FIXTURE_UUID,
    version="",
    version_latest="",
    version_newer_available=False,
    users=[],
)

FIXTURE_DATA_RESPONSE = Response(
    id="1234",
    type=TYPE_DATA_UPDATE,
    subtype=None,
    message="Data received",
    module=MODEL_SYSTEM,
    data=asdict(FIXTURE_SYSTEM),
)

FIXTURE_DATA_RESPONSE_BAD = Response(
    id="1234",
    type=TYPE_DATA_UPDATE,
    subtype=None,
    message="Data received",
    module=MODEL_SYSTEM,
    data={},
)

FIXTURE_DATA_RESPONSE_BAD = Response(
    id="1234",
    type=TYPE_DATA_UPDATE,
    subtype=None,
    message="Data received",
    module=MODEL_SYSTEM,
    data={},
)


async def mock_data_listener(
    self,
    callback: Callable[[str, Any], Awaitable[None]] | None = None,
    _: bool = False,
):
    """Mock websocket data listener."""
    if callback is not None:
        # Simulate data received from the websocket
        await callback(MODEL_SYSTEM, FIXTURE_SYSTEM)


async def test_show_user_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_flow(hass: HomeAssistant) -> None:
    """Test full user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.system_bridge.config_flow.WebSocketClient.connect"
    ), patch(
        "systembridgeconnector.websocket_client.WebSocketClient.get_data",
        return_value=FIXTURE_DATA_RESPONSE,
    ), patch(
        "systembridgeconnector.websocket_client.WebSocketClient.listen",
        new=mock_data_listener,
    ), patch(
        "homeassistant.components.system_bridge.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT
        )
    await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test-bridge"
    assert result2["data"] == FIXTURE_USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "systembridgeconnector.websocket_client.WebSocketClient.connect",
        side_effect=ConnectionErrorException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT
        )
    await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_connection_closed_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle connection closed cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.system_bridge.config_flow.WebSocketClient.connect"
    ), patch(
        "systembridgeconnector.websocket_client.WebSocketClient.get_data",
        side_effect=ConnectionClosedException,
    ), patch(
        "systembridgeconnector.websocket_client.WebSocketClient.listen",
        new=mock_data_listener,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT
        )
    await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_timeout_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle timeout cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.system_bridge.config_flow.WebSocketClient.connect"
    ), patch(
        "systembridgeconnector.websocket_client.WebSocketClient.get_data",
        side_effect=TimeoutError,
    ), patch(
        "systembridgeconnector.websocket_client.WebSocketClient.listen",
        new=mock_data_listener,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT
        )
    await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.system_bridge.config_flow.WebSocketClient.connect"
    ), patch(
        "systembridgeconnector.websocket_client.WebSocketClient.get_data",
        side_effect=AuthenticationException,
    ), patch(
        "systembridgeconnector.websocket_client.WebSocketClient.listen",
        new=mock_data_listener,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT
        )
    await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_uuid_error(hass: HomeAssistant) -> None:
    """Test we handle error from bad uuid."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.system_bridge.config_flow.WebSocketClient.connect"
    ), patch(
        "systembridgeconnector.websocket_client.WebSocketClient.get_data",
        side_effect=ValueError,
    ), patch(
        "systembridgeconnector.websocket_client.WebSocketClient.listen",
        new=mock_data_listener,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT
        )
    await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle unknown errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.system_bridge.config_flow.WebSocketClient.connect"
    ), patch(
        "systembridgeconnector.websocket_client.WebSocketClient.get_data",
        side_effect=Exception,
    ), patch(
        "systembridgeconnector.websocket_client.WebSocketClient.listen",
        new=mock_data_listener,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT
        )
    await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "unknown"}


async def test_reauth_authorization_error(hass: HomeAssistant) -> None:
    """Test we show user form on authorization error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reauth"}, data=FIXTURE_USER_INPUT
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "authenticate"

    with patch(
        "homeassistant.components.system_bridge.config_flow.WebSocketClient.connect"
    ), patch(
        "systembridgeconnector.websocket_client.WebSocketClient.get_data",
        side_effect=AuthenticationException,
    ), patch(
        "systembridgeconnector.websocket_client.WebSocketClient.listen",
        new=mock_data_listener,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_AUTH_INPUT
        )
    await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["step_id"] == "authenticate"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_reauth_connection_error(hass: HomeAssistant) -> None:
    """Test we show user form on connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reauth"}, data=FIXTURE_USER_INPUT
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "authenticate"

    with patch(
        "systembridgeconnector.websocket_client.WebSocketClient.connect",
        side_effect=ConnectionErrorException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_AUTH_INPUT
        )
    await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["step_id"] == "authenticate"
    assert result2["errors"] == {"base": "cannot_connect"}

    with patch(
        "systembridgeconnector.websocket_client.WebSocketClient.connect",
    ), patch(
        "systembridgeconnector.websocket_client.WebSocketClient.get_data",
        return_value=None,
    ), patch(
        "systembridgeconnector.websocket_client.WebSocketClient.listen",
        new=mock_data_listener,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_AUTH_INPUT
        )
    await hass.async_block_till_done()

    assert result3["type"] == data_entry_flow.FlowResultType.FORM
    assert result3["step_id"] == "authenticate"
    assert result3["errors"] == {"base": "cannot_connect"}


async def test_reauth_connection_closed_error(hass: HomeAssistant) -> None:
    """Test we show user form on connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reauth"}, data=FIXTURE_USER_INPUT
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "authenticate"

    with patch(
        "homeassistant.components.system_bridge.config_flow.WebSocketClient.connect"
    ), patch(
        "systembridgeconnector.websocket_client.WebSocketClient.get_data",
        side_effect=ConnectionClosedException,
    ), patch(
        "systembridgeconnector.websocket_client.WebSocketClient.listen",
        new=mock_data_listener,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_AUTH_INPUT
        )
    await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
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

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "authenticate"

    with patch(
        "homeassistant.components.system_bridge.config_flow.WebSocketClient.connect"
    ), patch(
        "systembridgeconnector.websocket_client.WebSocketClient.get_data",
        return_value=FIXTURE_DATA_RESPONSE,
    ), patch(
        "systembridgeconnector.websocket_client.WebSocketClient.listen",
        new=mock_data_listener,
    ), patch(
        "homeassistant.components.system_bridge.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_AUTH_INPUT
        )
    await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"


async def test_zeroconf_flow(hass: HomeAssistant) -> None:
    """Test zeroconf flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=FIXTURE_ZEROCONF,
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert not result["errors"]

    with patch(
        "homeassistant.components.system_bridge.config_flow.WebSocketClient.connect"
    ), patch(
        "systembridgeconnector.websocket_client.WebSocketClient.get_data",
        return_value=FIXTURE_DATA_RESPONSE,
    ), patch(
        "systembridgeconnector.websocket_client.WebSocketClient.listen",
        new=mock_data_listener,
    ), patch(
        "homeassistant.components.system_bridge.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_AUTH_INPUT
        )
    await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "1.1.1.1"
    assert result2["data"] == FIXTURE_ZEROCONF_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_cannot_connect(hass: HomeAssistant) -> None:
    """Test zeroconf cannot connect flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=FIXTURE_ZEROCONF,
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert not result["errors"]

    with patch(
        "systembridgeconnector.websocket_client.WebSocketClient.connect",
        side_effect=ConnectionErrorException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_AUTH_INPUT
        )
    await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["step_id"] == "authenticate"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_zeroconf_bad_zeroconf_info(hass: HomeAssistant) -> None:
    """Test zeroconf cannot connect flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=FIXTURE_ZEROCONF_BAD,
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_migration(hass: HomeAssistant) -> None:
    """Test migration from system_bridge to system_bridge."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FIXTURE_UUID,
        data={
            CONF_API_KEY: FIXTURE_USER_INPUT[CONF_TOKEN],
            CONF_HOST: FIXTURE_USER_INPUT[CONF_HOST],
            CONF_PORT: FIXTURE_USER_INPUT[CONF_PORT],
        },
        version=1,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check that the version has been updated and the api_key has been moved to token
    assert config_entry.version == SystemBridgeConfigFlow.VERSION
    assert config_entry.minor_version == SystemBridgeConfigFlow.MINOR_VERSION
    assert CONF_API_KEY not in config_entry.data
    assert config_entry.data[CONF_TOKEN] == FIXTURE_USER_INPUT[CONF_TOKEN]
    assert config_entry.data == FIXTURE_USER_INPUT
