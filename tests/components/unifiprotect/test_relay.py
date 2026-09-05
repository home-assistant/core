"""Tests for UniFi Protect relay entities from the Public API."""

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, Mock

import pytest
from uiprotect.data import (
    DeviceState,
    ModelType,
    PublicBootstrap,
    PublicRelayInput,
    PublicRelayOutput,
    Relay,
    RelayInputState,
    RelayOutputState,
)
from uiprotect.exceptions import ClientError, NotAuthorized
from uiprotect.websocket import WebsocketState

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.unifiprotect.const import DOMAIN
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
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .utils import MockUFPFixture, init_entry

RELAY_ID = "relay-id-1"
RELAY_MAC = "AA:BB:CC:DD:EE:01"
RELAY_NAME = "Garage Relay"
OUTPUT_ID = 1
OUTPUT_NAME = "output1"
INPUT_ID = 1
INPUT_NAME = "input1"

SWITCH_ENTITY_ID = "switch.garage_relay_output_output1"
BINARY_SENSOR_ENTITY_ID = "binary_sensor.garage_relay_input_input1"


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


def _make_input(
    input_id: int = INPUT_ID,
    name: str | None = INPUT_NAME,
    state: RelayInputState | None = RelayInputState.OFF,
) -> Mock:
    """Build a mock :class:`PublicRelayInput`."""
    relay_input = Mock(spec=PublicRelayInput)
    relay_input.id = input_id
    relay_input.name = name
    relay_input.state = state
    return relay_input


def _make_relay(
    *,
    outputs: list[Mock] | None = None,
    inputs: list[Mock] | None = None,
    state: DeviceState = DeviceState.CONNECTED,
) -> Mock:
    """Build a mock :class:`Relay` whose ``activate_output`` is awaitable."""
    relay = Mock(spec=Relay)
    relay.id = RELAY_ID
    relay.mac = RELAY_MAC
    relay.name = RELAY_NAME
    relay.model = ModelType.RELAY
    relay.state = state
    relay.outputs = outputs if outputs is not None else [_make_output()]
    relay.inputs = inputs if inputs is not None else [_make_input()]

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


def _make_real_relay(ufp: MockUFPFixture) -> Relay:
    """Build a relay using the pinned uiprotect public model."""
    return Relay.from_unifi_dict(
        api=ufp.api,
        id=RELAY_ID,
        modelKey="relay",
        state="CONNECTED",
        mac=RELAY_MAC,
        name=RELAY_NAME,
        ledSettings={"isEnabled": True},
        outputs=[],
        inputs=[
            {"id": 0, "name": "Garage Door Fully Open", "state": "off"},
            {"id": 1, "name": "Garage Door Fully Closed", "state": "off"},
        ],
    )


@pytest.fixture(name="ufp_with_relay")
def _ufp_with_relay(ufp: MockUFPFixture) -> tuple[MockUFPFixture, Mock]:
    """Configure ufp fixture with a single relay accessible via public API."""
    relay = _make_relay()
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = _make_public_bootstrap(relay)
    return ufp, relay


def _send_relay_update(ufp: MockUFPFixture, relay: Mock) -> None:
    """Dispatch a public devices websocket update for a relay."""
    message = Mock()
    message.changed_data = {}
    message.old_obj = relay
    message.new_obj = relay
    assert ufp.devices_ws_subscription is not None
    ufp.devices_ws_subscription(message)


async def test_relay_input_not_created_without_public_bootstrap(
    hass: HomeAssistant, ufp: MockUFPFixture
) -> None:
    """Relay inputs require the public bootstrap."""
    ufp.api.has_public_bootstrap = False

    await init_entry(hass, ufp, [])

    assert hass.states.get(BINARY_SENSOR_ENTITY_ID) is None


@pytest.mark.parametrize(
    ("inputs", "entity_ids"),
    [
        pytest.param(
            [],
            [],
            id="no_inputs",
        ),
        pytest.param(
            [_make_input(input_id=4, name="Door")],
            ["binary_sensor.garage_relay_input_door"],
            id="one_input",
        ),
        pytest.param(
            [
                _make_input(input_id=4, name="Door"),
                _make_input(input_id=7, name=None),
            ],
            [
                "binary_sensor.garage_relay_input_door",
                "binary_sensor.garage_relay_input_7",
            ],
            id="multiple_inputs",
        ),
    ],
)
async def test_relay_input_enumeration_names_and_unique_ids(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    inputs: list[Mock],
    entity_ids: list[str],
) -> None:
    """Create one stably identified entity per named or unnamed input."""
    relay = _make_relay(inputs=inputs)
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = _make_public_bootstrap(relay)

    await init_entry(hass, ufp, [])

    entries = [entity_registry.async_get(entity_id) for entity_id in entity_ids]
    assert all(entry is not None for entry in entries)
    assert [entry.unique_id for entry in entries if entry is not None] == [
        f"{RELAY_MAC}_relay_input_{relay_input.id}" for relay_input in inputs
    ]
    assert len(
        [
            entry
            for entry in entity_registry.entities.values()
            if entry.unique_id.startswith(f"{RELAY_MAC}_relay_input_")
        ]
    ) == len(inputs)


async def test_relay_input_unique_id_does_not_depend_on_name(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
) -> None:
    """Configured input names affect only entity names, not unique IDs."""
    ufp, relay = ufp_with_relay
    relay.inputs[0].name = "Side door"

    await init_entry(hass, ufp, [])

    entry = entity_registry.async_get("binary_sensor.garage_relay_input_side_door")
    assert entry is not None
    assert entry.unique_id == f"{RELAY_MAC}_relay_input_{INPUT_ID}"
    assert entry.original_name == "Input Side door"


@pytest.mark.parametrize(
    ("input_state", "expected_state"),
    [
        pytest.param(RelayInputState.ON, STATE_ON, id="on"),
        pytest.param(RelayInputState.OFF, STATE_OFF, id="off"),
        pytest.param(RelayInputState.UNKNOWN, STATE_UNKNOWN, id="unknown"),
        pytest.param(None, STATE_UNKNOWN, id="none"),
    ],
)
async def test_relay_input_initial_state(
    hass: HomeAssistant,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
    input_state: RelayInputState | None,
    expected_state: str,
) -> None:
    """Map sustained public input states to binary sensor states."""
    ufp, relay = ufp_with_relay
    relay.inputs[0].state = input_state

    await init_entry(hass, ufp, [])

    state = hass.states.get(BINARY_SENSOR_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state
    assert state.attributes.get("device_class") is None


async def test_relay_input_transitions_both_ways_from_public_ws(
    hass: HomeAssistant,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
) -> None:
    """Public devices websocket updates drive both input transitions."""
    ufp, relay = ufp_with_relay
    await init_entry(hass, ufp, [])
    state = hass.states.get(BINARY_SENSOR_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF

    relay.inputs[0].state = RelayInputState.ON
    _send_relay_update(ufp, relay)
    await hass.async_block_till_done()
    state = hass.states.get(BINARY_SENSOR_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON

    relay.inputs[0].state = RelayInputState.OFF
    _send_relay_update(ufp, relay)
    await hass.async_block_till_done()
    state = hass.states.get(BINARY_SENSOR_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


async def test_relay_input_update_preserves_other_input(
    hass: HomeAssistant, ufp: MockUFPFixture
) -> None:
    """A realistic full inputs update retains both input channels."""
    relay = _make_real_relay(ufp)
    ufp.api.has_public_bootstrap = True
    public_bootstrap = PublicBootstrap(relays={relay.id: relay})
    ufp.api.public_bootstrap = public_bootstrap
    await init_entry(hass, ufp, [])

    _model, new_obj, old_obj = public_bootstrap.process_devices_ws_message(
        ufp.api,
        {
            "type": "update",
            "item": {
                "id": RELAY_ID,
                "modelKey": "relay",
                "inputs": [
                    {"id": 0, "name": "Garage Door Fully Open", "state": "on"},
                    {"id": 1, "name": "Garage Door Fully Closed", "state": "off"},
                ],
            },
        },
    )
    assert isinstance(new_obj, Relay)
    message = Mock()
    message.changed_data = {"inputs": new_obj.inputs}
    message.old_obj = old_obj
    message.new_obj = new_obj
    assert ufp.devices_ws_subscription is not None
    ufp.devices_ws_subscription(message)
    await hass.async_block_till_done()

    assert [relay_input.id for relay_input in new_obj.inputs] == [0, 1]
    first_state = hass.states.get(
        "binary_sensor.garage_relay_input_garage_door_fully_open"
    )
    second_state = hass.states.get(
        "binary_sensor.garage_relay_input_garage_door_fully_closed"
    )
    assert first_state is not None
    assert second_state is not None
    assert first_state.state == STATE_ON
    assert second_state.state == STATE_OFF


async def test_relay_entities_created_for_relay_added_from_public_ws(
    hass: HomeAssistant, ufp: MockUFPFixture
) -> None:
    """A relay added after setup creates its input and output entities."""
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = _make_public_bootstrap(None)
    await init_entry(hass, ufp, [])

    relay = _make_relay()
    ufp.api.public_bootstrap.relays[relay.id] = relay
    _send_relay_update(ufp, relay)
    await hass.async_block_till_done()

    assert hass.states.get(BINARY_SENSOR_ENTITY_ID) is not None
    assert hass.states.get(SWITCH_ENTITY_ID) is not None


async def test_relay_input_created_when_added_after_setup(
    hass: HomeAssistant, ufp: MockUFPFixture
) -> None:
    """An input added to an existing relay creates a binary sensor."""
    relay = _make_relay(inputs=[])
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = _make_public_bootstrap(relay)
    await init_entry(hass, ufp, [])
    assert hass.states.get(BINARY_SENSOR_ENTITY_ID) is None

    relay.inputs = [_make_input()]
    _send_relay_update(ufp, relay)
    await hass.async_block_till_done()

    assert hass.states.get(BINARY_SENSOR_ENTITY_ID) is not None


async def test_relay_input_unavailable_when_relay_disconnected(
    hass: HomeAssistant,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
) -> None:
    """A disconnected relay makes its input unavailable."""
    ufp, relay = ufp_with_relay
    await init_entry(hass, ufp, [])

    relay.state = DeviceState.DISCONNECTED
    _send_relay_update(ufp, relay)
    await hass.async_block_till_done()

    state = hass.states.get(BINARY_SENSOR_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_relay_input_devices_ws_disconnect_reconnect_resync(
    hass: HomeAssistant,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
) -> None:
    """Input availability and state recover from the resynced public bootstrap."""
    ufp, relay = ufp_with_relay
    await init_entry(hass, ufp, [])

    assert ufp.devices_ws_state_subscription is not None
    ufp.devices_ws_state_subscription(WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()
    state = hass.states.get(BINARY_SENSOR_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    async def resync_public_bootstrap() -> Mock:
        relay.inputs[0].state = RelayInputState.ON
        return ufp.api.public_bootstrap

    ufp.api.update_public.side_effect = resync_public_bootstrap
    ufp.devices_ws_state_subscription(WebsocketState.CONNECTED)
    await hass.async_block_till_done()

    state = hass.states.get(BINARY_SENSOR_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    ufp.api.update_public.assert_awaited()


async def test_public_only_relay_channels_resignaled_after_reconnect(
    hass: HomeAssistant,
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Awaitable[None]],
) -> None:
    """A public-only reconnect re-offers channels on an existing relay."""
    relay = _make_relay(inputs=[])
    public_bootstrap = ufp_public_only.api.public_bootstrap
    public_bootstrap.relays = {relay.id: relay}
    await setup_public_only()

    signaled_relays: list[Relay] = []
    ufp_public_only.entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            ufp_public_only.entry.runtime_data.relay_signal,
            signaled_relays.append,
        )
    )

    async def resync_public_bootstrap() -> Mock:
        relay.inputs = [_make_input()]
        return public_bootstrap

    ufp_public_only.api.update_public.side_effect = resync_public_bootstrap
    assert ufp_public_only.devices_ws_state_subscription is not None
    ufp_public_only.devices_ws_state_subscription(WebsocketState.DISCONNECTED)
    ufp_public_only.devices_ws_state_subscription(WebsocketState.CONNECTED)
    await hass.async_block_till_done()

    assert signaled_relays == [relay]
    assert [relay_input.id for relay_input in signaled_relays[0].inputs] == [INPUT_ID]


@pytest.mark.parametrize(
    "remove_channel",
    [
        pytest.param(
            lambda ufp, _relay: setattr(ufp.api.public_bootstrap, "relays", {}),
            id="relay_removed",
        ),
        pytest.param(
            lambda _ufp, relay: setattr(relay, "inputs", []),
            id="input_removed",
        ),
    ],
)
async def test_relay_input_unavailable_when_channel_missing(
    hass: HomeAssistant,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
    remove_channel: Callable[[MockUFPFixture, Mock], None],
) -> None:
    """A removed relay or input makes the existing entity unavailable."""
    ufp, relay = ufp_with_relay
    relay.inputs[0].state = RelayInputState.ON
    await init_entry(hass, ufp, [])

    remove_channel(ufp, relay)
    _send_relay_update(ufp, relay)
    await hass.async_block_till_done()

    state = hass.states.get(BINARY_SENSOR_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_relay_input_uses_same_relay_and_nvr_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
) -> None:
    """Input and output share the relay device linked to the NVR."""
    ufp, _relay = ufp_with_relay
    await init_entry(hass, ufp, [])

    input_entry = entity_registry.async_get(BINARY_SENSOR_ENTITY_ID)
    output_entry = entity_registry.async_get(SWITCH_ENTITY_ID)
    assert input_entry is not None
    assert output_entry is not None
    assert input_entry.device_id == output_entry.device_id

    relay_device = device_registry.async_get(input_entry.device_id)
    nvr_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, ufp.api.bootstrap.nvr.mac), ufp.entry.entry_id
    )
    assert relay_device is not None
    assert nvr_device is not None
    assert relay_device.connections == {(dr.CONNECTION_NETWORK_MAC, RELAY_MAC.lower())}
    assert relay_device.identifiers == {(DOMAIN, RELAY_MAC)}
    assert relay_device.manufacturer == "Ubiquiti"
    assert relay_device.model == "Relay"
    assert relay_device.via_device_id == nvr_device.id


async def test_relay_input_ignores_events_ws_health(
    hass: HomeAssistant,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
) -> None:
    """Events websocket health does not affect sustained relay input state."""
    ufp, relay = ufp_with_relay
    relay.inputs[0].state = RelayInputState.ON
    await init_entry(hass, ufp, [])

    assert ufp.events_ws_state_subscription is not None
    ufp.events_ws_state_subscription(WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()

    state = hass.states.get(BINARY_SENSOR_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


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


async def test_relay_switch_device_links_to_nvr_via_device_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
) -> None:
    """Relay device's via_device_id points at the NVR device."""
    ufp, _relay = ufp_with_relay
    await init_entry(hass, ufp, [])

    nvr = ufp.api.bootstrap.nvr
    nvr_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, nvr.mac), ufp.entry.entry_id
    )
    assert nvr_device is not None

    relay_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, RELAY_MAC), ufp.entry.entry_id
    )
    assert relay_device is not None
    assert relay_device.via_device_id == nvr_device.id


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
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: SWITCH_ENTITY_ID},
        blocking=True,
    )
    relay.activate_output.assert_awaited_once_with(OUTPUT_ID, state="on")
    relay.activate_output.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
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
            SWITCH_DOMAIN,
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
            SWITCH_DOMAIN,
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
            SWITCH_DOMAIN,
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
            SWITCH_DOMAIN,
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

    assert ufp.devices_ws_state_subscription is not None
    ufp.devices_ws_state_subscription(WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()

    state = hass.states.get(SWITCH_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    ufp.devices_ws_state_subscription(WebsocketState.CONNECTED)
    await hass.async_block_till_done()

    state = hass.states.get(SWITCH_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


async def test_relay_switch_availability_decoupled_from_private_websocket(
    hass: HomeAssistant,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
) -> None:
    """Relay availability follows the public WS only: private loss is a no-op."""
    ufp, relay = ufp_with_relay
    relay.outputs[0].state = RelayOutputState.ON
    await init_entry(hass, ufp, [])
    assert hass.states.get(SWITCH_ENTITY_ID).state == STATE_ON  # type: ignore[union-attr]

    # A private WS loss does not affect the relay.
    assert ufp.ws_state_subscription is not None
    ufp.ws_state_subscription(WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()
    state = hass.states.get(SWITCH_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON

    # The public WS loss does flip it unavailable.
    ufp.devices_ws_state_subscription(WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()
    state = hass.states.get(SWITCH_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_relay_ws_update_without_subscription_is_ignored(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
) -> None:
    """A public relay WS update for an unsubscribed relay is a no-op."""
    await init_entry(hass, ufp, [])
    assert ufp.devices_ws_subscription is not None

    mock_msg = Mock()
    mock_msg.new_obj = _make_relay()
    ufp.devices_ws_subscription(mock_msg)
    await hass.async_block_till_done()

    assert hass.states.get(SWITCH_ENTITY_ID) is None


async def test_public_ws_state_change_without_public_bootstrap(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
) -> None:
    """Public WS state changes flip the flag but no-op without a bootstrap."""
    await init_entry(hass, ufp, [])
    data = ufp.entry.runtime_data
    assert data.last_public_update_success is True
    assert ufp.devices_ws_state_subscription is not None

    # No public bootstrap -> re-signal step returns early.
    ufp.devices_ws_state_subscription(WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()
    assert data.last_public_update_success is False

    # Same state again -> handler early-returns.
    ufp.devices_ws_state_subscription(WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()
    assert data.last_public_update_success is False


async def test_events_ws_state_change_without_public_bootstrap(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
) -> None:
    """Events WS state changes flip the flag but no-op without a bootstrap."""
    await init_entry(hass, ufp, [])
    data = ufp.entry.runtime_data
    assert data.last_events_update_success is True
    assert ufp.events_ws_state_subscription is not None

    # No public bootstrap -> re-signal step returns early.
    ufp.events_ws_state_subscription(WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()
    assert data.last_events_update_success is False

    # Same state again -> handler early-returns.
    ufp.events_ws_state_subscription(WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()
    assert data.last_events_update_success is False


async def test_relay_public_ws_message_without_public_old_obj(
    hass: HomeAssistant,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
) -> None:
    """A new_obj=None message without a PublicDeviceModel old_obj is ignored."""
    ufp, _ = ufp_with_relay
    await init_entry(hass, ufp, [])

    state_before = hass.states.get(SWITCH_ENTITY_ID)
    assert state_before is not None

    mock_msg = Mock()
    mock_msg.new_obj = None
    mock_msg.old_obj = None

    assert ufp.devices_ws_subscription is not None
    ufp.devices_ws_subscription(mock_msg)
    await hass.async_block_till_done()

    # Entity state must be unchanged.
    assert hass.states.get(SWITCH_ENTITY_ID) == state_before


def _outputs_removed_ws_message(ufp: MockUFPFixture, relay: Mock) -> Mock:
    """Build an update whose merged relay no longer contains any outputs.

    The library merges the update into the public bootstrap before
    dispatching, so mirror that here: entities re-read the bootstrap on
    dispatch.
    """
    relay_no_outputs = _make_relay(outputs=[])
    relay_no_outputs.id = relay.id
    relay_no_outputs.mac = relay.mac
    ufp.api.public_bootstrap.relays[relay.id] = relay_no_outputs

    mock_msg = Mock()
    mock_msg.new_obj = relay_no_outputs
    return mock_msg


def _relay_deleted_ws_message(ufp: MockUFPFixture, relay: Mock) -> Mock:
    """Build a delete event (new_obj=None) for the relay.

    The library removes the object from the bootstrap before dispatching;
    data.py dispatches None and the entity re-reads the relay as missing.
    """
    del ufp.api.public_bootstrap.relays[relay.id]

    mock_msg = Mock()
    mock_msg.old_obj = relay
    mock_msg.new_obj = None
    return mock_msg


@pytest.mark.parametrize(
    "make_ws_message",
    [
        pytest.param(_outputs_removed_ws_message, id="outputs_removed"),
        pytest.param(_relay_deleted_ws_message, id="relay_deleted"),
    ],
)
async def test_relay_switch_unavailable_after_ws_message(
    hass: HomeAssistant,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
    make_ws_message: Callable[[MockUFPFixture, Mock], Mock],
) -> None:
    """WS messages that leave no usable relay output mark the entity unavailable."""
    ufp, relay = ufp_with_relay
    relay.outputs[0].state = RelayOutputState.ON
    await init_entry(hass, ufp, [])

    assert hass.states.get(SWITCH_ENTITY_ID).state == STATE_ON  # type: ignore[union-attr]

    mock_msg = make_ws_message(ufp, relay)

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
    """Command raises HomeAssistantError when relay output channel is gone."""
    ufp, relay = ufp_with_relay
    await init_entry(hass, ufp, [])

    # Remove all outputs from the relay so get_output returns None.
    relay.outputs = []

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: SWITCH_ENTITY_ID},
            blocking=True,
        )
