"""Tests for the OSRAM Infrared light platform."""

from infrared_protocols.codes.osram.light import OSRAM_ADDRESS, OsramLightCode
from infrared_protocols.commands.nec import NECCommand
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.infrared import InfraredReceivedSignal
from homeassistant.components.light import (
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    EFFECT_OFF,
)
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
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.common import assert_availability_follows_source_entity
from tests.components.infrared import EMITTER_ENTITY_ID, RECEIVER_ENTITY_ID
from tests.components.infrared.common import (
    MockInfraredEmitterEntity,
    MockInfraredReceiverEntity,
)


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return [Platform.LIGHT]


@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test all light entities are created with correct attributes."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    device_entry = device_registry.async_get_device(
        identifiers={("osram_infrared", mock_config_entry.entry_id)}
    )
    assert device_entry

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_entry.device_id == device_entry.id


@pytest.mark.usefixtures("init_integration")
async def test_turn_on_sends_on_code(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test turning on the light sends the OSRAM on code."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.osram_light"},
        blocking=True,
    )

    assert (
        mock_infrared_emitter_entity.send_command_calls
        == [
            OsramLightCode.ON,
        ]
        * 5
    )

    state = hass.states.get("light.osram_light")
    assert state
    assert state.state == STATE_ON


@pytest.mark.usefixtures("init_integration")
async def test_turn_off_sends_off_code(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test turning off the light sends the OSRAM off code."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.osram_light"},
        blocking=True,
    )

    assert (
        mock_infrared_emitter_entity.send_command_calls
        == [
            OsramLightCode.OFF,
        ]
        * 5
    )

    state = hass.states.get("light.osram_light")
    assert state
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    ("hs_color", "expected_code", "expected_hs_color"),
    [
        ((42.0, 20.0), OsramLightCode.WHITE, (0.0, 0.0)),
        ((92.0, 100.0), OsramLightCode.HUE_120, (120.0, 100.0)),
        ((350.0, 100.0), OsramLightCode.HUE_000, (0.0, 100.0)),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_turn_on_with_hs_color_sends_nearest_color_code(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    hs_color: tuple[float, float],
    expected_code: OsramLightCode,
    expected_hs_color: tuple[float, float],
) -> None:
    """Test setting HS color sends the nearest supported OSRAM color code."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.osram_light",
            ATTR_HS_COLOR: hs_color,
        },
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [
        *([OsramLightCode.ON] * 5),
        *([expected_code] * 5),
    ]

    state = hass.states.get("light.osram_light")
    assert state
    assert tuple(state.attributes[ATTR_HS_COLOR]) == expected_hs_color


@pytest.mark.parametrize(
    ("effect", "expected_code"),
    [
        ("flash", OsramLightCode.FLASH),
        ("strobe", OsramLightCode.STROBE),
        ("smooth", OsramLightCode.SMOOTH),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_turn_on_with_effect_sends_effect_code(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    effect: str,
    expected_code: OsramLightCode,
) -> None:
    """Test setting an OSRAM effect sends the matching effect code."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.osram_light",
            ATTR_EFFECT: effect,
        },
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == [
        *([OsramLightCode.ON] * 5),
        expected_code,
    ]

    state = hass.states.get("light.osram_light")
    assert state
    assert state.attributes[ATTR_EFFECT] == effect


@pytest.mark.usefixtures("init_integration")
async def test_turn_on_with_effect_off_restores_last_static_color(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test turning an effect off restores the last static color."""
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.osram_light",
            ATTR_HS_COLOR: (92.0, 100.0),
        },
        blocking=True,
    )

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.osram_light",
            ATTR_EFFECT: "flash",
        },
        blocking=True,
    )

    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.osram_light",
            ATTR_EFFECT: EFFECT_OFF,
        },
        blocking=True,
    )

    assert (
        mock_infrared_emitter_entity.send_command_calls
        == [
            OsramLightCode.HUE_120,
        ]
        * 5
    )

    state = hass.states.get("light.osram_light")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_EFFECT] == EFFECT_OFF
    assert tuple(state.attributes[ATTR_HS_COLOR]) == (120.0, 100.0)


@pytest.mark.usefixtures("init_integration")
async def test_light_availability_follows_ir_entity(
    hass: HomeAssistant,
) -> None:
    """Test light becomes unavailable when IR entity is unavailable."""
    await assert_availability_follows_source_entity(
        hass,
        "light.osram_light",
        EMITTER_ENTITY_ID,
    )


@pytest.mark.usefixtures("init_integration")
async def test_receiver_off_code_updates_light_state(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test receiving the OSRAM off command updates the assumed light state."""
    command = NECCommand(
        address=OSRAM_ADDRESS,
        command=OsramLightCode.OFF,
    )

    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(timings=command.get_raw_timings())
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.osram_light")

    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    ("received_code", "expected_hs_color"),
    [
        (OsramLightCode.WHITE, (0.0, 0.0)),
        (OsramLightCode.HUE_120, (120.0, 100.0)),
        (OsramLightCode.HUE_300, (300.0, 100.0)),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_receiver_static_color_code_updates_light_state(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    received_code: OsramLightCode,
    expected_hs_color: tuple[float, float],
) -> None:
    """Test receiving static color commands updates the assumed color state."""
    command = NECCommand(
        address=OSRAM_ADDRESS,
        command=received_code,
    )

    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(timings=command.get_raw_timings())
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.osram_light")

    assert state is not None
    assert state.state == STATE_ON
    assert tuple(state.attributes[ATTR_HS_COLOR]) == expected_hs_color
    assert state.attributes[ATTR_EFFECT] == "off"


@pytest.mark.parametrize(
    ("received_code", "expected_effect"),
    [
        (OsramLightCode.FLASH, "flash"),
        (OsramLightCode.STROBE, "strobe"),
        (OsramLightCode.SMOOTH, "smooth"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_receiver_effect_code_updates_light_state(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    received_code: OsramLightCode,
    expected_effect: str,
) -> None:
    """Test receiving effect commands updates the assumed effect state."""
    command = NECCommand(
        address=OSRAM_ADDRESS,
        command=received_code,
    )

    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(timings=command.get_raw_timings())
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.osram_light")

    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_EFFECT] == expected_effect


@pytest.mark.usefixtures("init_integration")
async def test_receiver_ignores_other_nec_addresses(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test receiver ignores NEC commands from other addresses."""
    command = NECCommand(
        address=0x1234,
        command=OsramLightCode.ON,
    )

    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(timings=command.get_raw_timings())
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.osram_light")

    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("init_integration")
async def test_receiver_ignores_non_nec_signals(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test receiver ignores signals that cannot be decoded as NEC."""
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(timings=[1, 2, 3, 4])
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.osram_light")

    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("init_integration")
async def test_receiver_resubscribes_after_receiver_unavailable(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test light resubscribes when the configured receiver becomes available again."""
    hass.states.async_set(RECEIVER_ENTITY_ID, STATE_UNAVAILABLE)
    await hass.async_block_till_done()

    hass.states.async_set(RECEIVER_ENTITY_ID, STATE_UNKNOWN)
    await hass.async_block_till_done()

    command = NECCommand(
        address=OSRAM_ADDRESS,
        command=OsramLightCode.ON,
    )

    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(timings=command.get_raw_timings())
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.osram_light")

    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.parametrize(
    "received_code",
    [
        OsramLightCode.ON,
        OsramLightCode.MODE,
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_receiver_on_like_codes_turn_light_on(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    received_code: OsramLightCode,
) -> None:
    """Test receiving ON-like commands marks the assumed light state as on."""
    command = NECCommand(
        address=OSRAM_ADDRESS,
        command=received_code,
    )

    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(timings=command.get_raw_timings())
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.osram_light")
    assert state is not None
    assert state.state == STATE_ON


@pytest.mark.usefixtures("init_integration")
async def test_receiver_ignores_unknown_osram_command(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test receiver ignores unknown OSRAM NEC commands."""
    command = NECCommand(
        address=OSRAM_ADDRESS,
        command=0xFF,
    )

    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(timings=command.get_raw_timings())
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.osram_light")
    assert state is not None
    assert state.state == STATE_OFF
