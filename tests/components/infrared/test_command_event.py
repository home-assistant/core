"""Tests for the infrared command event entity."""

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from infrared_protocols.commands.nec import NECCommand
import pytest

from homeassistant.components.event import ATTR_EVENT_TYPE, ATTR_EVENT_TYPES
from homeassistant.components.infrared import DOMAIN, InfraredCommandEventEntity
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .common import (
    MockInfraredReceiverEntity,
    captured_code,
    received_signal,
    seed_commands,
)

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    mock_config_flow,
    mock_integration,
    mock_platform,
)
from tests.typing import WebSocketGenerator

TEST_DOMAIN = "test"
RECEIVER_UNIQUE_ID = "receiver-1"
EVENT_ENTITY_ID = "event.test_device"
RECEIVER_ENTITY_ID = "infrared.test_device_test_ir_receiver"

POWER_COMMAND = NECCommand(address=0x04FB, command=0xF7)
VOLUME_UP_COMMAND = NECCommand(address=0x04FB, command=0xF6)
UNKNOWN_COMMAND = NECCommand(address=0x04FB, command=0xF5)

DEVICE_INFO = DeviceInfo(identifiers={(TEST_DOMAIN, "device-1")}, name="Test device")

STORED_COMMANDS = [
    {"id": "power", "name": "Power", "code": captured_code(POWER_COMMAND)},
    {"id": "volume_up", "name": "Volume up", "code": captured_code(VOLUME_UP_COMMAND)},
]


class MockFlow(ConfigFlow):
    """Test flow."""


class MockReceiver(MockInfraredReceiverEntity):
    """Mock infrared receiver on the device of the provider integration."""

    _attr_device_info = DEVICE_INFO


@pytest.fixture
def receiver() -> MockReceiver:
    """Return the receiver the provider integration adds."""
    return MockReceiver(RECEIVER_UNIQUE_ID)


@pytest.fixture
async def provider(
    hass: HomeAssistant, hass_storage: dict[str, Any], receiver: MockReceiver
) -> None:
    """Mock an integration providing an infrared receiver and its event entity."""
    seed_commands(hass_storage, STORED_COMMANDS)
    assert await async_setup_component(hass, DOMAIN, {})

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up the platforms the entry asks for."""
        await hass.config_entries.async_forward_entry_setups(
            config_entry, config_entry.data["platforms"]
        )
        return True

    async def async_unload_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Unload the platforms of the entry."""
        return await hass.config_entries.async_unload_platforms(
            config_entry, config_entry.data["platforms"]
        )

    async def async_setup_entry_event(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
    ) -> None:
        """Add the event entity of the receiver."""
        async_add_entities(
            [InfraredCommandEventEntity(RECEIVER_UNIQUE_ID, DEVICE_INFO)]
        )

    async def async_setup_entry_infrared(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
    ) -> None:
        """Add the receiver."""
        async_add_entities([receiver])

    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")
    mock_integration(
        hass,
        MockModule(
            TEST_DOMAIN,
            async_setup_entry=async_setup_entry_init,
            async_unload_entry=async_unload_entry_init,
        ),
    )
    mock_platform(
        hass,
        f"{TEST_DOMAIN}.event",
        MockPlatform(async_setup_entry=async_setup_entry_event),
    )
    mock_platform(
        hass,
        f"{TEST_DOMAIN}.infrared",
        MockPlatform(async_setup_entry=async_setup_entry_infrared),
    )


async def setup_platforms(
    hass: HomeAssistant, platforms: list[Platform]
) -> MockConfigEntry:
    """Set up an entry of the provider integration with the given platforms."""
    entry = MockConfigEntry(
        domain=TEST_DOMAIN,
        data={"platforms": platforms},
        unique_id="-".join(platforms),
    )
    entry.add_to_hass(hass)
    with mock_config_flow(TEST_DOMAIN, MockFlow):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


@pytest.fixture
async def event_entry(hass: HomeAssistant, provider: None) -> MockConfigEntry:
    """Set up the event entity without the receiver."""
    return await setup_platforms(hass, [Platform.EVENT])


@pytest.fixture
async def receiver_entry(hass: HomeAssistant, provider: None) -> MockConfigEntry:
    """Set up the receiver and its event entity."""
    return await setup_platforms(hass, [Platform.INFRARED, Platform.EVENT])


@pytest.mark.usefixtures("freezer", "receiver_entry")
async def test_fires_for_a_known_command(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    receiver: MockReceiver,
) -> None:
    """Test the event entity fires with the name of the received command."""
    entry = entity_registry.async_get(EVENT_ENTITY_ID)
    assert entry is not None
    assert entry.unique_id == f"{RECEIVER_UNIQUE_ID}-commands"
    # The event entity belongs to the device of its receiver.
    assert entry.device_id == entity_registry.async_get(RECEIVER_ENTITY_ID).device_id

    assert (state := hass.states.get(EVENT_ENTITY_ID)) is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_EVENT_TYPES] == ["Power", "Volume up"]

    now = dt_util.utcnow()
    receiver._handle_received_signal(received_signal(POWER_COMMAND))

    assert (state := hass.states.get(EVENT_ENTITY_ID)) is not None
    assert state.state == now.isoformat(timespec="milliseconds")
    assert state.attributes[ATTR_EVENT_TYPE] == "Power"
    assert state.attributes["command_id"] == "power"


@pytest.mark.usefixtures("receiver_entry")
async def test_ignores_an_unknown_command(
    hass: HomeAssistant, receiver: MockReceiver
) -> None:
    """Test a signal that is not a known command does not fire the event."""
    receiver._handle_received_signal(received_signal(UNKNOWN_COMMAND))

    assert (state := hass.states.get(EVENT_ENTITY_ID)) is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("delay", "expected_delay"),
    [
        pytest.param(0.1, 0.0, id="button_held"),
        pytest.param(0.4, 0.4, id="button_pressed_again"),
    ],
)
@pytest.mark.usefixtures("receiver_entry")
async def test_repeated_command(
    hass: HomeAssistant,
    receiver: MockReceiver,
    freezer: FrozenDateTimeFactory,
    delay: float,
    expected_delay: float,
) -> None:
    """Test a command that comes back fires only once within the repeat window."""
    first = dt_util.utcnow()
    receiver._handle_received_signal(received_signal(POWER_COMMAND))

    freezer.tick(delay)
    receiver._handle_received_signal(received_signal(POWER_COMMAND))

    expected = first + timedelta(seconds=expected_delay)
    assert (state := hass.states.get(EVENT_ENTITY_ID)) is not None
    assert state.state == expected.isoformat(timespec="milliseconds")


@pytest.mark.usefixtures("receiver_entry")
async def test_event_types_follow_the_commands(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the event types are the names of the known commands."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "infrared/commands/create",
            "name": "Mute",
            "code": captured_code(UNKNOWN_COMMAND),
        }
    )
    assert (await client.receive_json())["success"]
    assert (state := hass.states.get(EVENT_ENTITY_ID)) is not None
    assert state.attributes[ATTR_EVENT_TYPES] == ["Power", "Volume up", "Mute"]

    await client.send_json_auto_id(
        {
            "type": "infrared/commands/update",
            "command_id": "power",
            "name": "Power toggle",
        }
    )
    assert (await client.receive_json())["success"]
    assert (state := hass.states.get(EVENT_ENTITY_ID)) is not None
    assert state.attributes[ATTR_EVENT_TYPES] == ["Power toggle", "Volume up", "Mute"]

    await client.send_json_auto_id(
        {"type": "infrared/commands/delete", "command_id": "volume_up"}
    )
    assert (await client.receive_json())["success"]
    assert (state := hass.states.get(EVENT_ENTITY_ID)) is not None
    assert state.attributes[ATTR_EVENT_TYPES] == ["Power toggle", "Mute"]


@pytest.mark.usefixtures("receiver_entry")
async def test_availability_follows_the_receiver(
    hass: HomeAssistant, receiver: MockReceiver
) -> None:
    """Test the event entity is unavailable while its receiver is."""
    receiver._attr_available = False
    receiver.async_write_ha_state()

    assert (state := hass.states.get(EVENT_ENTITY_ID)) is not None
    assert state.state == STATE_UNAVAILABLE

    receiver._attr_available = True
    receiver.async_write_ha_state()

    assert (state := hass.states.get(EVENT_ENTITY_ID)) is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("event_entry", "freezer")
async def test_receiver_added_after_the_event_entity(
    hass: HomeAssistant, receiver: MockReceiver
) -> None:
    """Test the event entity waits for a receiver that is not added yet."""
    assert (state := hass.states.get(EVENT_ENTITY_ID)) is not None
    assert state.state == STATE_UNAVAILABLE

    await setup_platforms(hass, [Platform.INFRARED])

    assert (state := hass.states.get(EVENT_ENTITY_ID)) is not None
    assert state.state == STATE_UNKNOWN

    now = dt_util.utcnow()
    receiver._handle_received_signal(received_signal(POWER_COMMAND))

    assert (state := hass.states.get(EVENT_ENTITY_ID)) is not None
    assert state.state == now.isoformat(timespec="milliseconds")


@pytest.mark.usefixtures("event_entry")
async def test_receiver_removed(hass: HomeAssistant, receiver: MockReceiver) -> None:
    """Test the event entity is unavailable once its receiver is removed."""
    receiver_entry = await setup_platforms(hass, [Platform.INFRARED])
    assert (state := hass.states.get(EVENT_ENTITY_ID)) is not None
    assert state.state == STATE_UNKNOWN

    assert await hass.config_entries.async_unload(receiver_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(EVENT_ENTITY_ID)) is not None
    assert state.state == STATE_UNAVAILABLE

    receiver._handle_received_signal(received_signal(POWER_COMMAND))
    assert (state := hass.states.get(EVENT_ENTITY_ID)) is not None
    assert state.state == STATE_UNAVAILABLE
