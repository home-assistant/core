"""Test switches through Home Assistant's state and service interfaces."""

from copy import deepcopy
from unittest.mock import MagicMock

from aiorexense import (
    Endpoint,
    RexenseAuthenticationError,
    RexenseCommandError,
    RexenseConnectionError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import ADDRESS, MAC

ENTITY_ID = "switch.tl0001_switch_1"


@pytest.fixture
async def setup_entry(
    hass: HomeAssistant, mock_gateway: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Set up the real switch platform using a mocked SDK."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("setup_entry")
@pytest.mark.parametrize(
    ("action", "value"),
    [
        pytest.param(SERVICE_TURN_ON, True, id="on"),
        pytest.param(SERVICE_TURN_OFF, False, id="off"),
    ],
)
async def test_control_waits_for_observed_state(
    hass: HomeAssistant, mock_gateway: MagicMock, action: str, value: bool
) -> None:
    """Send the selected command once without inventing a state update."""
    await hass.services.async_call(
        SWITCH_DOMAIN, action, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    mock_gateway.async_execute.assert_awaited_once_with(ADDRESS, {"on": value})
    assert hass.states.get(ENTITY_ID).state == STATE_ON


@pytest.mark.usefixtures("setup_entry")
@pytest.mark.parametrize(
    ("value", "state"),
    [
        pytest.param(True, STATE_ON, id="on"),
        pytest.param(False, STATE_OFF, id="off"),
        pytest.param(None, STATE_UNKNOWN, id="missing"),
        pytest.param(1, STATE_UNKNOWN, id="invalid-number"),
        pytest.param("true", STATE_UNKNOWN, id="invalid-string"),
    ],
)
async def test_push_state(
    hass: HomeAssistant, mock_gateway: MagicMock, value: object, state: str
) -> None:
    """Render a fresh SDK snapshot without retaining an obsolete endpoint object."""
    endpoint = deepcopy(mock_gateway.endpoints[ADDRESS])
    endpoint.properties = {"on": value}
    mock_gateway.endpoints = {ADDRESS: endpoint}
    mock_gateway.subscribe.call_args.args[0]()
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == state


@pytest.mark.usefixtures("setup_entry")
async def test_connection_and_endpoint_availability(
    hass: HomeAssistant, mock_gateway: MagicMock
) -> None:
    """Make the entity unavailable during gateway or endpoint outages."""
    callback = mock_gateway.subscribe.call_args.args[0]
    mock_gateway.connected = False
    callback()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    mock_gateway.connected = True
    mock_gateway.endpoints[ADDRESS].state = "offline"
    callback()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    mock_gateway.endpoints[ADDRESS].state = "online"
    callback()
    assert hass.states.get(ENTITY_ID).state == STATE_ON

    mock_gateway.endpoints.clear()
    callback()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("setup_entry")
@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(RexenseConnectionError(), id="connection"),
        pytest.param(RexenseAuthenticationError(), id="authentication"),
        pytest.param(RexenseCommandError(500), id="rejected"),
    ],
)
async def test_control_error(
    hass: HomeAssistant, mock_gateway: MagicMock, exception: Exception
) -> None:
    """Surface a translated action error and do not retry a write."""
    mock_gateway.async_execute.side_effect = exception
    with pytest.raises(HomeAssistantError, match="Unable to control"):
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )
    mock_gateway.async_execute.assert_awaited_once()
    assert hass.states.get(ENTITY_ID).state == STATE_ON


@pytest.mark.parametrize(
    ("dev_type", "confirmed", "definition"),
    [
        pytest.param("light", True, {"type": "bool", "access": "rw"}, id="light"),
        pytest.param(
            "switch", False, {"type": "bool", "access": "rw"}, id="unconfirmed"
        ),
        pytest.param("switch", True, {"type": "bool", "access": "r"}, id="read-only"),
        pytest.param("switch", True, {"type": "number", "access": "rw"}, id="numeric"),
    ],
)
async def test_unsupported_endpoints(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
    endpoint: Endpoint,
    dev_type: str,
    confirmed: bool,
    definition: dict[str, str],
) -> None:
    """Only confirmed writable boolean switch endpoints become entities."""
    endpoint.metadata["dev_type"] = dev_type
    endpoint.confirmed = confirmed
    endpoint.definitions["onoff"]["properties"]["on"] = definition
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert not hass.states.async_entity_ids("switch")
    mock_gateway.subscribe.assert_not_called()


async def test_endpoint_alias(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
    endpoint: Endpoint,
) -> None:
    """Use an endpoint's configured alias without changing its unique ID."""
    endpoint.metadata["lalias"] = "Kitchen"
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("switch.tl0001_kitchen").state == STATE_ON


async def test_multiple_switches(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
    endpoint: Endpoint,
) -> None:
    """Keep on/off channels independent while sharing their physical device."""
    second = deepcopy(endpoint)
    second.addr = f"{MAC}:2"
    second.properties = {"on": False}
    mock_gateway.endpoints[second.addr] = second
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_ON
    assert hass.states.get("switch.tl0001_switch_2").state == STATE_OFF
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.tl0001_switch_2"},
        blocking=True,
    )
    mock_gateway.async_execute.assert_awaited_once_with(second.addr, {"on": True})
