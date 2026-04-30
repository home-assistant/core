"""Tests for the UniFi Protect relay (Public API) switch entities."""

from unittest.mock import AsyncMock, Mock

import pytest
from uiprotect.data import (
    ModelType,
    PublicBootstrap,
    PublicRelayOutput,
    Relay,
    RelayOutputState,
)
from uiprotect.exceptions import ClientError, NotAuthorized
from uiprotect.websocket import WebsocketState

from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .utils import MockUFPFixture, init_entry

RELAY_ID = "relay-id-1"
RELAY_MAC = "AA:BB:CC:DD:EE:01"
RELAY_NAME = "Garage Relay"
OUTPUT_ID = 1
OUTPUT_NAME = "output1"

SWITCH_ENTITY_ID = "switch.garage_relay_output_output1"


def _make_output(
    output_id: int = OUTPUT_ID,
    name: str | None = OUTPUT_NAME,
    state: RelayOutputState | None = RelayOutputState.OFF,
) -> Mock:
    """Build a mock :class:`PublicRelayOutput`."""
    output = Mock(spec=PublicRelayOutput)
    output.id = output_id
    output.name = name
    output.state = state
    return output


def _make_relay(
    *,
    outputs: list[Mock] | None = None,
) -> Mock:
    """Build a mock :class:`Relay` whose ``activate_output`` is awaitable."""
    relay = Mock(spec=Relay)
    relay.id = RELAY_ID
    relay.mac = RELAY_MAC
    relay.name = RELAY_NAME
    relay.model = ModelType.RELAY
    relay.outputs = outputs if outputs is not None else [_make_output()]

    def get_output(output_id: int) -> Mock | None:
        return next((o for o in relay.outputs if o.id == output_id), None)

    relay.get_output = get_output
    relay.activate_output = AsyncMock()
    return relay


def _make_public_bootstrap(relay: Mock | None) -> Mock:
    """Build a public bootstrap mock holding the given relay."""
    pb = Mock(spec=PublicBootstrap)
    pb.relays = {relay.id: relay} if relay is not None else {}
    pb.arm_mode = None
    pb.arm_profiles = {}
    pb.sirens = {}
    return pb


@pytest.fixture(name="ufp_with_relay")
def _ufp_with_relay(ufp: MockUFPFixture) -> tuple[MockUFPFixture, Mock]:
    """Configure ufp fixture with a single relay accessible via public API."""
    relay = _make_relay()
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = _make_public_bootstrap(relay)
    return ufp, relay


# ---------------------------------------------------------------------------
# Switch
# ---------------------------------------------------------------------------


async def test_relay_switch_not_created_without_public_bootstrap(
    hass: HomeAssistant, ufp: MockUFPFixture
) -> None:
    """No relay output switch is created when public bootstrap is unavailable."""
    ufp.api.has_public_bootstrap = False
    await init_entry(hass, ufp, [])

    assert hass.states.get(SWITCH_ENTITY_ID) is None


async def test_relay_switch_created_with_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
) -> None:
    """Relay output switch is created and reflects the cached state."""
    ufp, relay = ufp_with_relay
    relay.outputs[0].state = RelayOutputState.ON

    await init_entry(hass, ufp, [])

    entry = entity_registry.async_get(SWITCH_ENTITY_ID)
    assert entry is not None
    assert entry.unique_id == f"{RELAY_MAC}_relay_output_{OUTPUT_ID}"

    state = hass.states.get(SWITCH_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


async def test_relay_switch_off_otp_is_off(
    hass: HomeAssistant,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
) -> None:
    """OFF_OTP (over-temperature protection) is treated as ``off``."""
    ufp, relay = ufp_with_relay
    relay.outputs[0].state = RelayOutputState.OFF_OTP

    await init_entry(hass, ufp, [])

    state = hass.states.get(SWITCH_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


async def test_relay_switch_unknown_state_is_unknown(
    hass: HomeAssistant,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
) -> None:
    """Unknown relay state should leave the switch state as ``unknown``."""
    ufp, relay = ufp_with_relay
    relay.outputs[0].state = RelayOutputState.UNKNOWN

    await init_entry(hass, ufp, [])

    state = hass.states.get(SWITCH_ENTITY_ID)
    assert state is not None
    # ``is_on`` is None while ``available`` is True → state is "unknown".
    # "unavailable" would mean the device is unreachable; UNKNOWN output state
    # means state data was received but cannot be interpreted.
    assert state.state == STATE_UNKNOWN


async def test_relay_switch_turn_on_off(
    hass: HomeAssistant,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
) -> None:
    """Calling ``turn_on``/``turn_off`` invokes the public-API helper."""
    ufp, relay = ufp_with_relay
    await init_entry(hass, ufp, [])

    await hass.services.async_call(
        Platform.SWITCH,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: SWITCH_ENTITY_ID},
        blocking=True,
    )
    relay.activate_output.assert_awaited_once_with(OUTPUT_ID, state="on")
    relay.activate_output.reset_mock()

    await hass.services.async_call(
        Platform.SWITCH,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: SWITCH_ENTITY_ID},
        blocking=True,
    )
    relay.activate_output.assert_awaited_once_with(OUTPUT_ID, state="off")


async def test_relay_switch_state_updates_from_public_ws(
    hass: HomeAssistant,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
) -> None:
    """A public devices WS update for the relay refreshes the switch state."""
    ufp, relay = ufp_with_relay
    relay.outputs[0].state = RelayOutputState.OFF
    await init_entry(hass, ufp, [])

    state = hass.states.get(SWITCH_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF

    relay.outputs[0].state = RelayOutputState.ON

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.old_obj = relay
    mock_msg.new_obj = relay
    assert ufp.devices_ws_subscription is not None
    ufp.devices_ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(SWITCH_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


async def test_relay_switch_creates_one_entity_per_output(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
) -> None:
    """Multiple outputs on a single relay yield multiple switch entities."""
    relay = _make_relay(
        outputs=[
            _make_output(output_id=1, name="output1"),
            _make_output(output_id=2, name="output2"),
        ],
    )
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = _make_public_bootstrap(relay)

    await init_entry(hass, ufp, [])

    assert entity_registry.async_get("switch.garage_relay_output_output1") is not None
    assert entity_registry.async_get("switch.garage_relay_output_output2") is not None


async def test_relay_switch_command_error_raises(
    hass: HomeAssistant,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
) -> None:
    """``activate_output`` errors are surfaced as :class:`HomeAssistantError`."""
    ufp, relay = ufp_with_relay
    await init_entry(hass, ufp, [])

    relay.activate_output.side_effect = NotAuthorized("denied")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            Platform.SWITCH,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: SWITCH_ENTITY_ID},
            blocking=True,
        )


async def test_relay_switch_client_error_raises(
    hass: HomeAssistant,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
) -> None:
    """``ClientError`` from ``activate_output`` is wrapped as HomeAssistantError."""
    ufp, relay = ufp_with_relay
    await init_entry(hass, ufp, [])

    relay.activate_output.side_effect = ClientError("timeout")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            Platform.SWITCH,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: SWITCH_ENTITY_ID},
            blocking=True,
        )


async def test_relay_switch_command_when_relay_gone(
    hass: HomeAssistant,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
) -> None:
    """Command raises HomeAssistantError when the relay is no longer in bootstrap."""
    ufp, _relay = ufp_with_relay
    await init_entry(hass, ufp, [])

    # Remove relay from bootstrap after setup.
    ufp.api.public_bootstrap.relays = {}

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            Platform.SWITCH,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: SWITCH_ENTITY_ID},
            blocking=True,
        )


async def test_relay_switch_command_when_bootstrap_unavailable(
    hass: HomeAssistant,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
) -> None:
    """Command raises HomeAssistantError when has_public_bootstrap is False."""
    ufp, _relay = ufp_with_relay
    await init_entry(hass, ufp, [])

    ufp.api.has_public_bootstrap = False

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            Platform.SWITCH,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: SWITCH_ENTITY_ID},
            blocking=True,
        )


async def test_relay_switch_ws_update_no_state_change(
    hass: HomeAssistant,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
) -> None:
    """WS update with the same state does not trigger an unnecessary state write."""
    ufp, relay = ufp_with_relay
    relay.outputs[0].state = RelayOutputState.ON
    await init_entry(hass, ufp, [])

    assert hass.states.get(SWITCH_ENTITY_ID).state == STATE_ON  # type: ignore[union-attr]

    # Fire update with identical state — entity state must not change.
    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.old_obj = relay
    mock_msg.new_obj = relay
    assert ufp.devices_ws_subscription is not None
    ufp.devices_ws_subscription(mock_msg)
    await hass.async_block_till_done()

    assert hass.states.get(SWITCH_ENTITY_ID).state == STATE_ON  # type: ignore[union-attr]


async def test_relay_switch_becomes_unavailable_when_relay_removed(
    hass: HomeAssistant,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
) -> None:
    """Entity becomes unavailable when the relay disappears from the bootstrap."""
    ufp, relay = ufp_with_relay
    relay.outputs[0].state = RelayOutputState.OFF
    await init_entry(hass, ufp, [])

    # Drop the relay from the public bootstrap.
    ufp.api.public_bootstrap.relays = {}

    # Send a WS update whose output list is still valid; the entity must still
    # become unavailable because _relay now resolves to None.
    relay2 = _make_relay()
    relay2.id = relay.id
    relay2.mac = relay.mac

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.old_obj = relay2
    mock_msg.new_obj = relay2
    assert ufp.devices_ws_subscription is not None
    ufp.devices_ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(SWITCH_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_relay_switch_availability_follows_websocket_state(
    hass: HomeAssistant,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
) -> None:
    """Relay switch becomes unavailable on WS disconnect and recovers on reconnect."""
    ufp, relay = ufp_with_relay
    relay.outputs[0].state = RelayOutputState.ON
    await init_entry(hass, ufp, [])

    assert hass.states.get(SWITCH_ENTITY_ID).state == STATE_ON  # type: ignore[union-attr]

    assert ufp.ws_state_subscription is not None
    ufp.ws_state_subscription(WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()

    state = hass.states.get(SWITCH_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    ufp.ws_state_subscription(WebsocketState.CONNECTED)
    await hass.async_block_till_done()

    state = hass.states.get(SWITCH_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


async def test_relay_public_ws_message_with_none_new_obj(
    hass: HomeAssistant,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
) -> None:
    """Public WS message with new_obj=None is silently ignored."""
    ufp, _ = ufp_with_relay
    await init_entry(hass, ufp, [])

    state_before = hass.states.get(SWITCH_ENTITY_ID)
    assert state_before is not None

    mock_msg = Mock()
    mock_msg.new_obj = None

    assert ufp.devices_ws_subscription is not None
    ufp.devices_ws_subscription(mock_msg)
    await hass.async_block_till_done()

    # Entity state must be unchanged.
    assert hass.states.get(SWITCH_ENTITY_ID) == state_before


async def test_relay_switch_output_removed_from_relay_update(
    hass: HomeAssistant,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
) -> None:
    """WS update where the output is no longer present marks the entity unavailable."""
    ufp, relay = ufp_with_relay
    relay.outputs[0].state = RelayOutputState.ON
    await init_entry(hass, ufp, [])

    assert hass.states.get(SWITCH_ENTITY_ID).state == STATE_ON  # type: ignore[union-attr]

    # Build a relay WS update that no longer contains any outputs.
    relay_no_outputs = _make_relay(outputs=[])
    relay_no_outputs.id = relay.id
    relay_no_outputs.mac = relay.mac

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.old_obj = relay_no_outputs
    mock_msg.new_obj = relay_no_outputs

    assert ufp.devices_ws_subscription is not None
    ufp.devices_ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(SWITCH_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_relay_switch_command_when_output_gone(
    hass: HomeAssistant,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
) -> None:
    """Command raises HomeAssistantError when the relay output channel is no longer present."""
    ufp, relay = ufp_with_relay
    await init_entry(hass, ufp, [])

    # Remove all outputs from the relay so get_output returns None.
    relay.outputs = []

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            Platform.SWITCH,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: SWITCH_ENTITY_ID},
            blocking=True,
        )
