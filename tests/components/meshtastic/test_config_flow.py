"""Test the Meshtastic config flow."""

import asyncio
from datetime import timedelta
import socket
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from meshtastic.mesh_interface import MeshInterface
from meshtastic.protobuf import mesh_pb2
import pytest

from homeassistant.components.meshtastic.client import MeshtasticClient
from homeassistant.components.meshtastic.config_flow import VALIDATION_TIMEOUT
from homeassistant.components.meshtastic.const import (
    CONF_DOWNLOAD_NODE_DB,
    CONF_INCLUDE_LOCATION,
    CONF_TRACK_POSITION,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util

from . import GATEWAY_ID

from tests.common import MockConfigEntry, async_fire_time_changed

OTHER_NUM = 3735928559

USER_INPUT = {
    CONF_HOST: "192.0.2.10",
    CONF_PORT: DEFAULT_PORT,
    CONF_DOWNLOAD_NODE_DB: False,
}

RECONFIGURE_INPUT = {CONF_HOST: "192.0.2.55", CONF_PORT: 4404}

CONNECT_ERRORS = [
    pytest.param(OSError("no route to host"), "cannot_connect", id="cannot_connect"),
    pytest.param(
        MeshInterface.MeshInterfaceError("Timed out waiting for connection completion"),
        "cannot_connect",
        id="handshake_failed",
    ),
    pytest.param(
        socket.gaierror(-2, "Name or service not known"),
        "invalid_host",
        id="invalid_host",
    ),
    pytest.param(
        ConnectionResetError("connection reset by peer"),
        "already_in_use",
        id="already_in_use",
    ),
    pytest.param(
        BrokenPipeError("broken pipe"), "already_in_use", id="already_in_use_pipe"
    ),
    pytest.param(
        TimeoutError("handshake timed out"), "timeout_connect", id="timeout_connect"
    ),
    pytest.param(Exception("something else entirely"), "unknown", id="unknown"),
]


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow(
    hass: HomeAssistant,
    mock_meshtastic_client: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the happy path of the user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_DOWNLOAD_NODE_DB: True}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "HA Gateway"
    assert result["result"].unique_id == GATEWAY_ID
    assert result["data"] == {
        CONF_HOST: "192.0.2.10",
        CONF_PORT: DEFAULT_PORT,
        CONF_DOWNLOAD_NODE_DB: True,
    }
    assert len(mock_setup_entry.mock_calls) == 1

    # The node database is never downloaded while testing the connection, even
    # when the user asked for it: a low memory node can crash on the dump.
    mock_meshtastic_client.interface_class.assert_called_once_with(
        hostname="192.0.2.10",
        portNumber=DEFAULT_PORT,
        noNodes=True,
        connectNow=True,
        timeout=45,
    )
    assert mock_meshtastic_client.close.call_count == 1


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(("side_effect", "error"), CONNECT_ERRORS)
async def test_user_flow_connection_errors(
    hass: HomeAssistant,
    mock_meshtastic_client: MagicMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test that every connection failure is reported and can be recovered from."""
    mock_meshtastic_client.interface_class.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    mock_meshtastic_client.interface_class.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == USER_INPUT


@pytest.mark.usefixtures("mock_setup_entry", "mock_meshtastic_client")
async def test_user_flow_validation_timeout(hass: HomeAssistant) -> None:
    """Test that a connection test which never answers is reported and retried.

    A node that accepts the TCP connection but never completes the handshake
    leaves the flow waiting, which is what ``VALIDATION_TIMEOUT`` is for.  The
    timer that bounds it is a real event-loop timer, so the test moves the
    clock past it instead of shortening it: shortening it only races the
    mocked connection, which always wins.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    never_connects = asyncio.Event()

    async def _hang(_client: MeshtasticClient) -> None:
        """Accept the connection and then never finish the handshake."""
        await never_connects.wait()

    with patch.object(MeshtasticClient, "async_start", _hang):
        configuring = hass.async_create_task(
            hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
        )
        for _ in range(3):
            await asyncio.sleep(0)
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=VALIDATION_TIMEOUT + 5)
        )
        result = await configuring

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "timeout_connect"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == USER_INPUT


@pytest.mark.usefixtures("mock_setup_entry", "mock_meshtastic_client")
async def test_user_flow_empty_host(hass: HomeAssistant) -> None:
    """Test that a blank host is rejected without touching the network."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_HOST: "   "}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_host"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry", "mock_meshtastic_client")
async def test_user_flow_duplicate(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that the same node cannot be configured twice."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_HOST: "192.0.2.99"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "192.0.2.10"


@pytest.mark.usefixtures("mock_setup_entry", "mock_meshtastic_client")
async def test_reconfigure_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test moving an existing entry to a new address."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], RECONFIGURE_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.unique_id == GATEWAY_ID
    assert mock_config_entry.data == {
        CONF_HOST: "192.0.2.55",
        CONF_PORT: 4404,
        CONF_DOWNLOAD_NODE_DB: False,
    }


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow_other_node(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
) -> None:
    """Test that reconfiguring onto a different node is refused."""
    mock_config_entry.add_to_hass(hass)
    mock_meshtastic_client.myInfo = mesh_pb2.MyNodeInfo(my_node_num=OTHER_NUM)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], RECONFIGURE_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data[CONF_HOST] == "192.0.2.10"


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(("side_effect", "error"), CONNECT_ERRORS)
async def test_reconfigure_flow_connection_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meshtastic_client: MagicMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test that a failing reconfigure shows the error and can be retried."""
    mock_config_entry.add_to_hass(hass)
    mock_meshtastic_client.interface_class.side_effect = side_effect

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], RECONFIGURE_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": error}

    mock_meshtastic_client.interface_class.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], RECONFIGURE_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == "192.0.2.55"


@pytest.mark.usefixtures("mock_setup_entry", "mock_meshtastic_client")
async def test_reconfigure_flow_empty_host(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that a blank host is rejected in the reconfigure step too."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**RECONFIGURE_INPUT, CONF_HOST: ""}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_host"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], RECONFIGURE_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("options", "suggested"),
    [
        pytest.param({}, False, id="from_entry_data"),
        pytest.param({CONF_DOWNLOAD_NODE_DB: True}, True, id="from_entry_options"),
    ],
)
async def test_options_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    options: dict[str, Any],
    suggested: bool,
) -> None:
    """Test the options flow round trip.

    Every option the integration reads is offered here: the node database
    download, position tracking, and whether the diagnostics download carries
    exact coordinates.
    """
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, options=options)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    schema = result["data_schema"].schema
    assert {str(marker) for marker in schema} == {
        CONF_DOWNLOAD_NODE_DB,
        CONF_TRACK_POSITION,
        CONF_INCLUDE_LOCATION,
    }
    suggestions = {str(marker): marker.description for marker in schema}
    assert suggestions[CONF_DOWNLOAD_NODE_DB] == {"suggested_value": suggested}
    assert suggestions[CONF_TRACK_POSITION] == {"suggested_value": True}
    assert suggestions[CONF_INCLUDE_LOCATION] == {"suggested_value": False}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_DOWNLOAD_NODE_DB: True,
            CONF_TRACK_POSITION: False,
            CONF_INCLUDE_LOCATION: True,
        },
    )
    await hass.async_block_till_done()

    expected = {
        CONF_DOWNLOAD_NODE_DB: True,
        CONF_TRACK_POSITION: False,
        CONF_INCLUDE_LOCATION: True,
    }
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == expected
    assert mock_config_entry.options == expected
    assert mock_config_entry.data[CONF_DOWNLOAD_NODE_DB] is False
