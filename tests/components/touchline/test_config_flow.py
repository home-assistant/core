"""Test the Touchline config flow."""

from dataclasses import replace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytouchline_extended import (
    DiscoveredController,
    RoomStatus,
    TouchlineConnectionError,
    TouchlineState,
)

from homeassistant import config_entries
from homeassistant.components.touchline.config_flow import MANUAL_ENTRY
from homeassistant.components.touchline.const import DOMAIN
from homeassistant.const import CONF_DEVICE, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .conftest import (
    DISCOVERED_CONTROLLER,
    ROOM_STATUS,
    TEST_HOST,
    TEST_UNIQUE_ID,
    make_state,
)

TEST_DATA = {CONF_HOST: TEST_HOST}

# Searching the network finds nothing unless a test says otherwise.
pytestmark = pytest.mark.usefixtures("mock_discover_controllers")


async def test_form_success(
    hass: HomeAssistant,
    mock_touchline_controller: MagicMock,
    mock_setup_entry: MagicMock,
) -> None:
    """Test entering a controller URL when none is found on the network."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_DATA,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_HOST
    assert result["data"] == TEST_DATA
    assert result["result"].unique_id == TEST_UNIQUE_ID
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "error_key"),
    [
        (TouchlineConnectionError, "cannot_connect"),
        (Exception("Unexpected backend explosion"), "unknown"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    mock_touchline_controller: MagicMock,
    side_effect: Exception,
    error_key: str,
) -> None:
    """Test errors during input validation are handled."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    mock_touchline_controller.fetch_async.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_DATA,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_key}

    # "Fix" the problem, and try again.
    mock_touchline_controller.fetch_async.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_DATA,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_HOST
    assert result["data"] == TEST_DATA
    assert result["result"].unique_id == TEST_UNIQUE_ID


@pytest.mark.parametrize(
    "rooms",
    [
        pytest.param((replace(ROOM_STATUS, controller_id=None),), id="missing-id"),
        pytest.param((), id="no-thermostats"),
    ],
)
async def test_form_missing_controller_id(
    hass: HomeAssistant,
    mock_touchline_controller: MagicMock,
    rooms: tuple[RoomStatus, ...],
) -> None:
    """Test a controller without a usable ID is reported as a connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_touchline_controller.fetch_async.return_value = make_state(*rooms)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_DATA,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_touchline_controller.fetch_async.return_value = make_state(ROOM_STATUS)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_DATA,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == TEST_UNIQUE_ID


async def test_already_configured_by_host(
    hass: HomeAssistant, mock_touchline_controller: MagicMock
) -> None:
    """Test abort when host is already configured."""
    MockConfigEntry(domain=DOMAIN, data=TEST_DATA).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_DATA,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_already_configured_by_unique_id(
    hass: HomeAssistant, mock_touchline_controller: MagicMock
) -> None:
    """Test abort when unique id is already configured."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "5.6.7.8"},
        unique_id=TEST_UNIQUE_ID,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_DATA,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


DHCP_DISCOVERY = DhcpServiceInfo(
    ip=TEST_HOST, hostname="roth-008149", macaddress="5cc213008149"
)
DISCOVERED_HOST = f"http://{TEST_HOST}"


async def test_dhcp_discovery(
    hass: HomeAssistant,
    mock_touchline_controller: MagicMock,
    mock_setup_entry: MagicMock,
) -> None:
    """Test setting up a controller discovered via DHCP."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DHCP_DISCOVERY,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DISCOVERED_HOST
    assert result["data"] == {CONF_HOST: DISCOVERED_HOST}
    assert result["result"].unique_id == TEST_UNIQUE_ID
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "state",
    [
        pytest.param(TouchlineConnectionError, id="connection-error"),
        pytest.param(make_state(), id="no-thermostats"),
    ],
)
async def test_dhcp_discovery_cannot_connect(
    hass: HomeAssistant,
    mock_touchline_controller: MagicMock,
    state: TouchlineState | type[Exception],
) -> None:
    """Test discovery aborts when the device does not answer like a controller."""
    mock_touchline_controller.fetch_async.side_effect = [state]

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DHCP_DISCOVERY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_dhcp_discovery_updates_host(
    hass: HomeAssistant, mock_touchline_controller: MagicMock
) -> None:
    """Test discovery updates the address of a configured controller."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "http://5.6.7.8"},
        unique_id=TEST_UNIQUE_ID,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DHCP_DISCOVERY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data == {CONF_HOST: DISCOVERED_HOST}


@pytest.mark.parametrize(
    ("source", "data"),
    [
        pytest.param(
            config_entries.SOURCE_USER, {CONF_HOST: "http://roth.local"}, id="hostname"
        ),
        pytest.param(config_entries.SOURCE_IGNORE, {}, id="ignored"),
    ],
)
async def test_dhcp_discovery_keeps_entry(
    hass: HomeAssistant,
    mock_touchline_controller: MagicMock,
    source: str,
    data: dict[str, str],
) -> None:
    """Test discovery does not replace a hostname or touch an ignored entry."""
    entry = MockConfigEntry(
        domain=DOMAIN, source=source, data=data, unique_id=TEST_UNIQUE_ID
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DHCP_DISCOVERY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data == data


async def test_manual_setup_while_discovery_pending(
    hass: HomeAssistant,
    mock_touchline_controller: MagicMock,
    mock_setup_entry: MagicMock,
) -> None:
    """Test a controller can be entered manually while its discovery card waits."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DHCP_DISCOVERY,
    )
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=TEST_DATA
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == TEST_UNIQUE_ID
    # Creating the entry closes the discovery card.
    assert not hass.config_entries.flow.async_progress()


async def test_dhcp_discovery_host_already_configured(
    hass: HomeAssistant, mock_touchline_controller: MagicMock
) -> None:
    """Test discovery of a configured address aborts without contacting it."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: DISCOVERED_HOST},
        unique_id=TEST_UNIQUE_ID,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DHCP_DISCOVERY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_touchline_controller.fetch_async.assert_not_called()


def _listed_options(result: config_entries.ConfigFlowResult) -> list[dict[str, str]]:
    """Return the options of the controller list."""
    return result["data_schema"].schema[CONF_DEVICE].config["options"]


async def test_pick_controller(
    hass: HomeAssistant,
    mock_touchline_controller: MagicMock,
    mock_discover_controllers: AsyncMock,
    mock_setup_entry: MagicMock,
) -> None:
    """Test setting up a controller found on the network."""
    mock_discover_controllers.return_value = [DISCOVERED_CONTROLLER]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    # Both networks are searched, and the controller is listed once.
    assert {
        call.kwargs["broadcast_address"]
        for call in mock_discover_controllers.call_args_list
    } == {"10.255.255.255", "192.168.1.255"}
    assert _listed_options(result) == [
        {"value": "1", "label": f"{DISCOVERED_HOST} (5C-C2-13-00-81-49)"},
        {"value": MANUAL_ENTRY, "label": MANUAL_ENTRY},
    ]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_DEVICE: "1"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DISCOVERED_HOST
    assert result["data"] == {CONF_HOST: DISCOVERED_HOST}
    assert result["result"].unique_id == TEST_UNIQUE_ID
    assert len(mock_setup_entry.mock_calls) == 1


async def test_pick_manual_entry(
    hass: HomeAssistant,
    mock_touchline_controller: MagicMock,
    mock_discover_controllers: AsyncMock,
    mock_setup_entry: MagicMock,
) -> None:
    """Test entering a URL when the list has controllers."""
    mock_discover_controllers.return_value = [DISCOVERED_CONTROLLER]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_DEVICE: MANUAL_ENTRY}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=TEST_DATA
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == TEST_DATA
    assert result["result"].unique_id == TEST_UNIQUE_ID


@pytest.mark.parametrize(
    "entry_data",
    [
        pytest.param(
            {"data": {CONF_HOST: "http://5.6.7.8"}, "unique_id": TEST_UNIQUE_ID},
            id="same-controller",
        ),
        pytest.param(
            {"data": {CONF_HOST: DISCOVERED_HOST}, "unique_id": "2"},
            id="same-address",
        ),
    ],
)
async def test_pick_skips_configured(
    hass: HomeAssistant,
    mock_discover_controllers: AsyncMock,
    entry_data: dict[str, Any],
) -> None:
    """Test controllers that are already set up are not listed."""
    MockConfigEntry(domain=DOMAIN, **entry_data).add_to_hass(hass)
    other_controller = replace(
        DISCOVERED_CONTROLLER, controller_id=3, url="http://1.2.3.5"
    )
    mock_discover_controllers.return_value = [DISCOVERED_CONTROLLER, other_controller]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert [option["value"] for option in _listed_options(result)] == [
        "3",
        MANUAL_ENTRY,
    ]


@pytest.mark.parametrize(
    ("return_value", "side_effect"),
    [
        pytest.param([], None, id="no-answer"),
        pytest.param(None, TouchlineConnectionError, id="search-failed"),
    ],
)
async def test_none_found_shows_manual_entry(
    hass: HomeAssistant,
    mock_discover_controllers: AsyncMock,
    return_value: list[DiscoveredController] | None,
    side_effect: type[Exception] | None,
) -> None:
    """Test the URL form is shown when no controller is found."""
    mock_discover_controllers.return_value = return_value
    mock_discover_controllers.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"


async def test_pick_one_network_fails(
    hass: HomeAssistant,
    mock_discover_controllers: AsyncMock,
) -> None:
    """Test a failed search on one network still lists what the others found."""

    async def discover(broadcast_address: str) -> list[DiscoveredController]:
        if broadcast_address == "10.255.255.255":
            raise TouchlineConnectionError
        return [DISCOVERED_CONTROLLER]

    mock_discover_controllers.side_effect = discover

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert [option["value"] for option in _listed_options(result)] == [
        "1",
        MANUAL_ENTRY,
    ]


async def test_pick_cannot_connect(
    hass: HomeAssistant,
    mock_touchline_controller: MagicMock,
    mock_discover_controllers: AsyncMock,
) -> None:
    """Test the flow aborts when the picked controller cannot be read."""
    mock_discover_controllers.return_value = [DISCOVERED_CONTROLLER]
    mock_touchline_controller.fetch_async.side_effect = TouchlineConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_DEVICE: "1"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_pick_already_configured(
    hass: HomeAssistant,
    mock_touchline_controller: MagicMock,
    mock_discover_controllers: AsyncMock,
) -> None:
    """Test the flow aborts when the picked controller turns out to be set up."""
    MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "http://5.6.7.8"}, unique_id=TEST_UNIQUE_ID
    ).add_to_hass(hass)
    # The search reports another ID than the controller itself.
    mock_discover_controllers.return_value = [
        replace(DISCOVERED_CONTROLLER, controller_id=2)
    ]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_DEVICE: "2"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
