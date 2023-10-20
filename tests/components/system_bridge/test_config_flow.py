"""Test the System Bridge config flow."""
import asyncio
from ipaddress import ip_address
from unittest.mock import patch

from systembridgeconnector.const import MODEL_SYSTEM, TYPE_DATA_UPDATE
from systembridgeconnector.exceptions import (
    AuthenticationException,
    ConnectionClosedException,
    ConnectionErrorException,
)
from systembridgeconnector.models.response import Response
from systembridgeconnector.models.system import LastUpdated, System

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import zeroconf
from homeassistant.components.system_bridge.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

FIXTURE_MAC_ADDRESS = "aa:bb:cc:dd:ee:ff"
FIXTURE_UUID = "e91bf575-56f3-4c83-8f42-70ac17adcd33"

FIXTURE_AUTH_INPUT = {CONF_API_KEY: "abc-123-def-456-ghi"}

FIXTURE_USER_INPUT = {
    CONF_API_KEY: "abc-123-def-456-ghi",
    CONF_HOST: "test-bridge",
    CONF_PORT: "9170",
}

FIXTURE_ZEROCONF_INPUT = {
    CONF_API_KEY: "abc-123-def-456-ghi",
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
    id=FIXTURE_UUID,
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
    last_updated=LastUpdated(
        boot_time=1,
        fqdn=1,
        hostname=1,
        ip_address_4=1,
        mac_address=1,
        platform=1,
        platform_version=1,
        uptime=1,
        uuid=1,
        version=1,
        version_latest=1,
        version_newer_available=1,
    ),
)

FIXTURE_DATA_RESPONSE = Response(
    id="1234",
    type=TYPE_DATA_UPDATE,
    subtype=None,
    message="Data received",
    module=MODEL_SYSTEM,
    data=FIXTURE_SYSTEM,
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
        "systembridgeconnector.websocket_client.WebSocketClient.listen"
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
        side_effect=asyncio.TimeoutError,
    ), patch(
        "systembridgeconnector.websocket_client.WebSocketClient.listen",
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
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_USER_INPUT
        )
    await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_value_error(hass: HomeAssistant) -> None:
    """Test we handle error from bad value."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.system_bridge.config_flow.WebSocketClient.connect"
    ), patch(
        "systembridgeconnector.websocket_client.WebSocketClient.get_data",
        return_value=FIXTURE_DATA_RESPONSE_BAD,
    ), patch(
        "systembridgeconnector.websocket_client.WebSocketClient.listen",
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
        "systembridgeconnector.websocket_client.WebSocketClient.listen"
    ), patch(
        "homeassistant.components.system_bridge.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_AUTH_INPUT
        )
    await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"

    assert len(mock_setup_entry.mock_calls) == 1


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
        "systembridgeconnector.websocket_client.WebSocketClient.listen"
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
