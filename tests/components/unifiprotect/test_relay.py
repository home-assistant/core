"""Tests for UniFi Protect relay entities from the Public API."""

from collections.abc import Callable, Coroutine
from typing import Any, NamedTuple
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
    WSAction,
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

from .utils import (
    MockUFPFixture,
    bind_public_device_properties,
    init_entry,
    make_public_bootstrap,
    public_device_ws_message,
)

RELAY_ID = "relay-id-1"
RELAY_MAC = "AA:BB:CC:DD:EE:01"
RELAY_NAME = "Garage Relay"
RELAY_TYPE = "USL-Relay-EU"
OUTPUT_ID = 2
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
    relay.type = RELAY_TYPE
    relay.model = ModelType.RELAY
    relay.state = state
    relay.outputs = outputs if outputs is not None else [_make_output()]
    relay.inputs = inputs if inputs is not None else [_make_input()]

    def get_output(output_id: int) -> Mock | None:
        return next((o for o in relay.outputs if o.id == output_id), None)

    def get_input(input_id: int) -> Mock | None:
        return next((i for i in relay.inputs if i.id == input_id), None)

    relay.get_output = get_output
    relay.get_input = get_input
    bind_public_device_properties(relay, Relay)
    relay.activate_output = AsyncMock()
    return relay


def _make_public_bootstrap(relay: Mock | None) -> Mock:
    """Build a public bootstrap mock holding the given relay."""
    return make_public_bootstrap(relays={relay.id: relay} if relay is not None else {})


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


class _Channel(NamedTuple):
    """A relay channel family and the entity for its first channel."""

    entity_id: str
    attr: str
    on: RelayInputState | RelayOutputState
    off: RelayInputState | RelayOutputState


_INPUT = _Channel(
    BINARY_SENSOR_ENTITY_ID, "inputs", RelayInputState.ON, RelayInputState.OFF
)
_OUTPUT = _Channel(
    SWITCH_ENTITY_ID, "outputs", RelayOutputState.ON, RelayOutputState.OFF
)
_CHANNELS = pytest.mark.parametrize(
    "channel",
    [pytest.param(_INPUT, id="input"), pytest.param(_OUTPUT, id="output")],
)


def _set_channel_state(
    relay: Mock, channel: _Channel, state: RelayInputState | RelayOutputState | None
) -> None:
    getattr(relay, channel.attr)[0].state = state


def _state(hass: HomeAssistant, entity_id: str) -> str:
    state = hass.states.get(entity_id)
    assert state is not None
    return state.state


def _send_relay_update(ufp: MockUFPFixture, relay: Mock) -> None:
    """Dispatch a public devices websocket update for a relay."""
    message = Mock()
    message.changed_data = {}
    message.old_obj = relay
    message.new_obj = relay
    assert ufp.devices_ws_subscription is not None
    ufp.devices_ws_subscription(message)


def _delete_relay(ufp: MockUFPFixture, relay: Mock, _channel: _Channel) -> None:
    """Dispatch a delete frame; the library drops the relay before dispatching."""
    del ufp.api.public_bootstrap.relays[relay.id]
    message = Mock()
    message.changed_data = {}
    message.old_obj = relay
    message.new_obj = None
    assert ufp.devices_ws_subscription is not None
    ufp.devices_ws_subscription(message)


def _remove_channel(ufp: MockUFPFixture, relay: Mock, channel: _Channel) -> None:
    """Dispatch an update whose merged relay no longer has the channel."""
    merged = _make_relay(**{channel.attr: []})
    ufp.api.public_bootstrap.relays[relay.id] = merged
    _send_relay_update(ufp, merged)


async def test_relay_entities_not_created_without_public_bootstrap(
    hass: HomeAssistant, ufp: MockUFPFixture
) -> None:
    """Relay inputs and outputs require the public bootstrap."""
    ufp.api.has_public_bootstrap = False

    await init_entry(hass, ufp, [])

    assert hass.states.get(BINARY_SENSOR_ENTITY_ID) is None
    assert hass.states.get(SWITCH_ENTITY_ID) is None


@pytest.mark.parametrize(
    ("relay_kwargs", "entity_ids", "unique_ids"),
    [
        pytest.param({"inputs": []}, [], [], id="no_inputs"),
        pytest.param(
            {"inputs": [_make_input(input_id=4, name="Door")]},
            ["binary_sensor.garage_relay_input_door"],
            [f"{RELAY_MAC}_relay_input_4"],
            id="one_input",
        ),
        pytest.param(
            {
                "inputs": [
                    _make_input(input_id=4, name="Door"),
                    _make_input(input_id=7, name=None),
                ]
            },
            [
                "binary_sensor.garage_relay_input_door",
                "binary_sensor.garage_relay_input_7",
            ],
            [f"{RELAY_MAC}_relay_input_4", f"{RELAY_MAC}_relay_input_7"],
            id="multiple_inputs",
        ),
        pytest.param(
            {
                "outputs": [
                    _make_output(output_id=1, name="Gate"),
                    _make_output(output_id=3, name=None),
                ]
            },
            ["switch.garage_relay_output_gate", "switch.garage_relay_output_3"],
            [f"{RELAY_MAC}_relay_output_1", f"{RELAY_MAC}_relay_output_3"],
            id="multiple_outputs",
        ),
    ],
)
async def test_relay_channel_enumeration_names_and_unique_ids(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    relay_kwargs: dict[str, list[Mock]],
    entity_ids: list[str],
    unique_ids: list[str],
) -> None:
    """Create one stably identified entity per named or unnamed channel."""
    relay = _make_relay(**relay_kwargs)
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = _make_public_bootstrap(relay)

    await init_entry(hass, ufp, [])

    entries = [entity_registry.async_get(entity_id) for entity_id in entity_ids]
    assert [entry.unique_id for entry in entries if entry is not None] == unique_ids
    (attr,) = relay_kwargs
    assert len(
        [
            entry
            for entry in entity_registry.entities.values()
            if entry.unique_id.startswith(f"{RELAY_MAC}_relay_{attr[:-1]}_")
        ]
    ) == len(unique_ids)


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
    ("entity_id", "attr", "channel_state", "expected_state"),
    [
        pytest.param(
            BINARY_SENSOR_ENTITY_ID,
            "inputs",
            RelayInputState.ON,
            STATE_ON,
            id="input_on",
        ),
        pytest.param(
            BINARY_SENSOR_ENTITY_ID,
            "inputs",
            RelayInputState.OFF,
            STATE_OFF,
            id="input_off",
        ),
        pytest.param(
            BINARY_SENSOR_ENTITY_ID,
            "inputs",
            RelayInputState.UNKNOWN,
            STATE_UNKNOWN,
            id="input_unknown",
        ),
        pytest.param(
            BINARY_SENSOR_ENTITY_ID, "inputs", None, STATE_UNKNOWN, id="input_none"
        ),
        pytest.param(
            SWITCH_ENTITY_ID, "outputs", RelayOutputState.ON, STATE_ON, id="output_on"
        ),
        pytest.param(
            SWITCH_ENTITY_ID,
            "outputs",
            RelayOutputState.OFF,
            STATE_OFF,
            id="output_off",
        ),
        # Over-temperature protection reads as off.
        pytest.param(
            SWITCH_ENTITY_ID,
            "outputs",
            RelayOutputState.OFF_OTP,
            STATE_OFF,
            id="output_off_otp",
        ),
        # Data that cannot be interpreted is unknown, not unavailable.
        pytest.param(
            SWITCH_ENTITY_ID,
            "outputs",
            RelayOutputState.UNKNOWN,
            STATE_UNKNOWN,
            id="output_unknown",
        ),
        pytest.param(
            SWITCH_ENTITY_ID, "outputs", None, STATE_UNKNOWN, id="output_none"
        ),
    ],
)
async def test_relay_channel_initial_state(
    hass: HomeAssistant,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
    entity_id: str,
    attr: str,
    channel_state: RelayInputState | RelayOutputState | None,
    expected_state: str,
) -> None:
    """Map public channel states to entity states."""
    ufp, relay = ufp_with_relay
    getattr(relay, attr)[0].state = channel_state

    await init_entry(hass, ufp, [])

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state
    assert state.attributes.get("device_class") is None


@_CHANNELS
async def test_relay_channel_transitions_both_ways_from_public_ws(
    hass: HomeAssistant,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
    channel: _Channel,
) -> None:
    """Public devices websocket updates drive both channel transitions."""
    ufp, relay = ufp_with_relay
    _set_channel_state(relay, channel, channel.off)
    await init_entry(hass, ufp, [])
    assert _state(hass, channel.entity_id) == STATE_OFF

    _set_channel_state(relay, channel, channel.on)
    _send_relay_update(ufp, relay)
    await hass.async_block_till_done()
    assert _state(hass, channel.entity_id) == STATE_ON

    _set_channel_state(relay, channel, channel.off)
    _send_relay_update(ufp, relay)
    await hass.async_block_till_done()
    assert _state(hass, channel.entity_id) == STATE_OFF


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


@_CHANNELS
async def test_relay_channel_unavailable_when_disconnected(
    hass: HomeAssistant,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
    channel: _Channel,
) -> None:
    """A relay that drops off the console is unavailable, and recovers."""
    ufp, relay = ufp_with_relay
    _set_channel_state(relay, channel, channel.on)
    await init_entry(hass, ufp, [])
    assert _state(hass, channel.entity_id) == STATE_ON

    relay.state = DeviceState.DISCONNECTED
    ufp.devices_ws_subscription(public_device_ws_message(relay))
    await hass.async_block_till_done()
    assert _state(hass, channel.entity_id) == STATE_UNAVAILABLE

    relay.state = DeviceState.CONNECTED
    ufp.devices_ws_subscription(public_device_ws_message(relay))
    await hass.async_block_till_done()
    assert _state(hass, channel.entity_id) == STATE_ON


@_CHANNELS
@pytest.mark.parametrize(
    "state",
    [DeviceState.DISCONNECTED, DeviceState.CONNECTING, DeviceState.UNKNOWN],
)
async def test_relay_channel_unavailable_when_not_connected_at_setup(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    channel: _Channel,
    state: DeviceState,
) -> None:
    """A relay that is not connected at setup starts out unavailable."""
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = _make_public_bootstrap(_make_relay(state=state))

    await init_entry(hass, ufp, [])

    assert _state(hass, channel.entity_id) == STATE_UNAVAILABLE


@_CHANNELS
async def test_relay_channel_devices_ws_disconnect_reconnect_resync(
    hass: HomeAssistant,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
    channel: _Channel,
) -> None:
    """Availability and state recover from the resynced public bootstrap."""
    ufp, relay = ufp_with_relay
    _set_channel_state(relay, channel, channel.off)
    await init_entry(hass, ufp, [])

    assert ufp.devices_ws_state_subscription is not None
    ufp.devices_ws_state_subscription(WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()
    assert _state(hass, channel.entity_id) == STATE_UNAVAILABLE

    async def resync_public_bootstrap() -> Mock:
        _set_channel_state(relay, channel, channel.on)
        return ufp.api.public_bootstrap

    ufp.api.update_public.side_effect = resync_public_bootstrap
    ufp.devices_ws_state_subscription(WebsocketState.CONNECTED)
    await hass.async_block_till_done()

    assert _state(hass, channel.entity_id) == STATE_ON
    ufp.api.update_public.assert_awaited()


@_CHANNELS
async def test_relay_channel_availability_follows_public_websocket_only(
    hass: HomeAssistant,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
    channel: _Channel,
) -> None:
    """Private and events websocket loss leave the relay alone."""
    ufp, relay = ufp_with_relay
    _set_channel_state(relay, channel, channel.on)
    await init_entry(hass, ufp, [])

    assert ufp.ws_state_subscription is not None
    assert ufp.events_ws_state_subscription is not None
    ufp.ws_state_subscription(WebsocketState.DISCONNECTED)
    ufp.events_ws_state_subscription(WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()
    assert _state(hass, channel.entity_id) == STATE_ON

    assert ufp.devices_ws_state_subscription is not None
    ufp.devices_ws_state_subscription(WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()
    assert _state(hass, channel.entity_id) == STATE_UNAVAILABLE


async def test_public_only_relay_channels_resignaled_after_reconnect(
    hass: HomeAssistant,
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    """A public-only reconnect re-offers channels on an existing relay."""
    relay = _make_relay(inputs=[])
    public_bootstrap = ufp_public_only.api.public_bootstrap
    public_bootstrap.relays = {relay.id: relay}
    await setup_public_only()
    assert hass.states.get(BINARY_SENSOR_ENTITY_ID) is None

    async def resync_public_bootstrap() -> Mock:
        relay.inputs = [_make_input()]
        return public_bootstrap

    ufp_public_only.api.update_public.side_effect = resync_public_bootstrap
    assert ufp_public_only.devices_ws_state_subscription is not None
    ufp_public_only.devices_ws_state_subscription(WebsocketState.DISCONNECTED)
    ufp_public_only.devices_ws_state_subscription(WebsocketState.CONNECTED)
    await hass.async_block_till_done()

    state = hass.states.get(BINARY_SENSOR_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


@_CHANNELS
@pytest.mark.parametrize(
    "remove",
    [
        pytest.param(_delete_relay, id="relay_deleted"),
        pytest.param(_remove_channel, id="channel_removed"),
    ],
)
async def test_relay_channel_unavailable_when_missing(
    hass: HomeAssistant,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
    channel: _Channel,
    remove: Callable[[MockUFPFixture, Mock, _Channel], None],
) -> None:
    """A deleted relay or a removed channel makes the existing entity unavailable."""
    ufp, relay = ufp_with_relay
    _set_channel_state(relay, channel, channel.on)
    await init_entry(hass, ufp, [])

    remove(ufp, relay, channel)
    await hass.async_block_till_done()

    assert _state(hass, channel.entity_id) == STATE_UNAVAILABLE


async def test_relay_readopted_with_new_id(
    hass: HomeAssistant,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
) -> None:
    """A relay re-adopted under a new id keeps its entities working."""
    ufp, relay = ufp_with_relay
    await init_entry(hass, ufp, [])
    _delete_relay(ufp, relay, _OUTPUT)
    await hass.async_block_till_done()

    readopted = _make_relay()
    readopted.id = "relay-id-2"
    _set_channel_state(readopted, _INPUT, RelayInputState.ON)
    _set_channel_state(readopted, _OUTPUT, RelayOutputState.ON)
    ufp.api.public_bootstrap.relays[readopted.id] = readopted
    msg = public_device_ws_message(readopted)
    msg.action = WSAction.ADD
    ufp.devices_ws_subscription(msg)
    await hass.async_block_till_done()

    assert _state(hass, BINARY_SENSOR_ENTITY_ID) == STATE_ON
    assert _state(hass, SWITCH_ENTITY_ID) == STATE_ON

    # A reconnect re-reads the bootstrap under the new id.
    assert ufp.devices_ws_state_subscription is not None
    ufp.devices_ws_state_subscription(WebsocketState.DISCONNECTED)
    ufp.devices_ws_state_subscription(WebsocketState.CONNECTED)
    await hass.async_block_till_done()
    assert _state(hass, SWITCH_ENTITY_ID) == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: SWITCH_ENTITY_ID},
        blocking=True,
    )
    readopted.activate_output.assert_awaited_once_with(OUTPUT_ID, state="off")


async def test_relay_readopted_during_websocket_outage(
    hass: HomeAssistant,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
) -> None:
    """A relay re-adopted while the devices websocket was down is found by mac."""
    ufp, relay = ufp_with_relay
    await init_entry(hass, ufp, [])

    readopted = _make_relay()
    readopted.id = "relay-id-2"
    _set_channel_state(readopted, _OUTPUT, RelayOutputState.ON)

    async def resync_public_bootstrap() -> Mock:
        ufp.api.public_bootstrap.relays = {readopted.id: readopted}
        return ufp.api.public_bootstrap

    ufp.api.update_public.side_effect = resync_public_bootstrap
    assert ufp.devices_ws_state_subscription is not None
    ufp.devices_ws_state_subscription(WebsocketState.DISCONNECTED)
    ufp.devices_ws_state_subscription(WebsocketState.CONNECTED)
    await hass.async_block_till_done()

    assert _state(hass, SWITCH_ENTITY_ID) == STATE_ON
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: SWITCH_ENTITY_ID},
        blocking=True,
    )
    readopted.activate_output.assert_awaited_once_with(OUTPUT_ID, state="off")
    relay.activate_output.assert_not_awaited()


async def test_relay_channels_share_relay_device_linked_to_nvr(
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
    assert relay_device.identifiers == set()
    assert relay_device.manufacturer == "Ubiquiti"
    assert relay_device.model == RELAY_TYPE
    assert relay_device.model_id == RELAY_TYPE
    assert relay_device.via_device_id == nvr_device.id


@pytest.mark.parametrize("output_id", [0, 3])
async def test_relay_switch_turn_on_off(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    output_id: int,
) -> None:
    """Calling ``turn_on``/``turn_off`` activates the entity's own output."""
    relay = _make_relay(outputs=[_make_output(output_id=output_id)])
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = _make_public_bootstrap(relay)
    await init_entry(hass, ufp, [])

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: SWITCH_ENTITY_ID},
        blocking=True,
    )
    relay.activate_output.assert_awaited_once_with(output_id, state="on")
    relay.activate_output.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: SWITCH_ENTITY_ID},
        blocking=True,
    )
    relay.activate_output.assert_awaited_once_with(output_id, state="off")


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(NotAuthorized("denied"), id="not_authorized"),
        pytest.param(ClientError("timeout"), id="client_error"),
    ],
)
async def test_relay_switch_command_error_raises(
    hass: HomeAssistant,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
    error: Exception,
) -> None:
    """``activate_output`` errors are surfaced as :class:`HomeAssistantError`."""
    ufp, relay = ufp_with_relay
    await init_entry(hass, ufp, [])
    relay.activate_output.side_effect = error

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: SWITCH_ENTITY_ID},
            blocking=True,
        )


@pytest.mark.parametrize(
    "break_relay",
    [
        pytest.param(
            lambda ufp, _relay: setattr(ufp.api.public_bootstrap, "relays", {}),
            id="relay_gone",
        ),
        pytest.param(
            lambda ufp, _relay: setattr(ufp.api, "has_public_bootstrap", False),
            id="bootstrap_unavailable",
        ),
        pytest.param(
            lambda _ufp, relay: setattr(relay, "outputs", []), id="output_gone"
        ),
    ],
)
async def test_relay_switch_command_without_output_raises(
    hass: HomeAssistant,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
    break_relay: Callable[[MockUFPFixture, Mock], None],
) -> None:
    """A command raises when the output can no longer be reached."""
    ufp, relay = ufp_with_relay
    await init_entry(hass, ufp, [])
    break_relay(ufp, relay)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: SWITCH_ENTITY_ID},
            blocking=True,
        )
    relay.activate_output.assert_not_awaited()


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


async def test_relay_switch_public_only(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp_public_only: MockUFPFixture,
    setup_public_only: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    """Relay output switches are public-API entities and work in API-key-only mode."""
    relay = _make_relay()
    relay.outputs[0].state = RelayOutputState.ON
    ufp_public_only.api.public_bootstrap.relays = {relay.id: relay}

    await setup_public_only()

    assert entity_registry.async_get(SWITCH_ENTITY_ID) is not None
    assert hass.states.get(SWITCH_ENTITY_ID).state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: SWITCH_ENTITY_ID},
        blocking=True,
    )
    relay.activate_output.assert_awaited_once_with(OUTPUT_ID, state="off")


@pytest.fixture(name="setup_hybrid")
def setup_hybrid_fixture(
    hass: HomeAssistant, ufp: MockUFPFixture
) -> Callable[[], Coroutine[Any, Any, None]]:
    """Return a callable setting up the hybrid entry with an empty public bootstrap."""
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = _make_public_bootstrap(None)

    async def _setup() -> None:
        await init_entry(hass, ufp, [])

    return _setup


def _add_relay_frame(ufp: MockUFPFixture, relay: Mock) -> None:
    """Deliver a public devices websocket add frame for ``relay``."""
    ufp.api.public_bootstrap.relays[relay.id] = relay
    msg = public_device_ws_message(relay)
    msg.action = WSAction.ADD
    ufp.devices_ws_subscription(msg)


@pytest.mark.parametrize(
    ("ufp_fixture", "setup_fixture"),
    [
        pytest.param("ufp_public_only", "setup_public_only", id="public_only"),
        pytest.param("ufp", "setup_hybrid", id="hybrid"),
    ],
)
async def test_relay_switch_added_after_setup(
    hass: HomeAssistant,
    request: pytest.FixtureRequest,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
    ufp_fixture: str,
    setup_fixture: str,
) -> None:
    """A relay adopted after setup gets its switches from its add frame in both modes.

    A relay has no private counterpart, so hybrid cannot discover it through
    the adopt path either. A re-delivered frame must not add a second time.
    """
    ufp: MockUFPFixture = request.getfixturevalue(ufp_fixture)
    setup: Callable[[], Coroutine[Any, Any, None]] = request.getfixturevalue(
        setup_fixture
    )
    await setup()
    assert entity_registry.async_get(SWITCH_ENTITY_ID) is None

    relay = _make_relay()
    _add_relay_frame(ufp, relay)
    await hass.async_block_till_done()

    assert entity_registry.async_get(SWITCH_ENTITY_ID) is not None
    count = len(hass.states.async_entity_ids(SWITCH_DOMAIN))

    _add_relay_frame(ufp, relay)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == count
    assert "already exists" not in caplog.text


async def test_relay_switch_hybrid_startup_relay_not_added_twice(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    ufp_with_relay: tuple[MockUFPFixture, Mock],
) -> None:
    """A relay enumerated at hybrid setup is in the add baseline.

    Its add frame (or the re-offer after a reconnect) must not create the
    switches a second time.
    """
    ufp, relay = ufp_with_relay
    await init_entry(hass, ufp, [])
    count = len(hass.states.async_entity_ids(SWITCH_DOMAIN))
    assert count

    _add_relay_frame(ufp, relay)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == count
    assert "already exists" not in caplog.text
