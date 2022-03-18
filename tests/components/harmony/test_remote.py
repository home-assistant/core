"""Test the Logitech Harmony Hub remote."""

from datetime import timedelta

from aioharmony.const import SendCommandDevice

from homeassistant.components.harmony.const import (
    DOMAIN,
    SERVICE_CHANGE_CHANNEL,
    SERVICE_SYNC,
)
from homeassistant.components.harmony.remote import ATTR_CHANNEL, ATTR_DELAY_SECS
from homeassistant.components.remote import (
    ATTR_ACTIVITY,
    ATTR_COMMAND,
    ATTR_DEVICE,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    DEFAULT_HOLD_SECS,
    DOMAIN as REMOTE_DOMAIN,
    SERVICE_SEND_COMMAND,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_NAME,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.util import utcnow

from .conftest import ACTIVITIES_TO_IDS, TV_DEVICE_ID, TV_DEVICE_NAME
from .const import ENTITY_REMOTE, HUB_NAME

from tests.common import MockConfigEntry, async_fire_time_changed

PLAY_COMMAND = "Play"
STOP_COMMAND = "Stop"


async def test_connection_state_changes(
    harmony_client, mock_hc, hass, mock_write_config
):
    """Ensure connection changes are reflected in the remote state."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.0.2.0", CONF_NAME: HUB_NAME}
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # mocks start with current activity == Watch TV
    assert hass.states.is_state(ENTITY_REMOTE, STATE_ON)

    harmony_client.mock_disconnection()
    await hass.async_block_till_done()

    # Entities do not immediately show as unavailable
    assert hass.states.is_state(ENTITY_REMOTE, STATE_ON)

    future_time = utcnow() + timedelta(seconds=10)
    async_fire_time_changed(hass, future_time)
    await hass.async_block_till_done()
    assert hass.states.is_state(ENTITY_REMOTE, STATE_UNAVAILABLE)

    harmony_client.mock_reconnection()
    await hass.async_block_till_done()

    assert hass.states.is_state(ENTITY_REMOTE, STATE_ON)

    harmony_client.mock_disconnection()
    harmony_client.mock_reconnection()
    future_time = utcnow() + timedelta(seconds=10)
    async_fire_time_changed(hass, future_time)

    await hass.async_block_till_done()
    assert hass.states.is_state(ENTITY_REMOTE, STATE_ON)


async def test_remote_toggles(mock_hc, hass, mock_write_config):
    """Ensure calls to the remote also updates the switches."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.0.2.0", CONF_NAME: HUB_NAME}
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # mocks start remote with Watch TV default activity
    state = hass.states.get(ENTITY_REMOTE)
    assert state.state == STATE_ON
    assert state.attributes.get("current_activity") == "Watch TV"

    # turn off remote
    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_REMOTE},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_REMOTE)
    assert state.state == STATE_OFF
    assert state.attributes.get("current_activity") == "PowerOff"

    # turn on remote, restoring the last activity
    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_REMOTE},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_REMOTE)
    assert state.state == STATE_ON
    assert state.attributes.get("current_activity") == "Watch TV"

    # send new activity command, with activity name
    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_REMOTE, ATTR_ACTIVITY: "Play Music"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_REMOTE)
    assert state.state == STATE_ON
    assert state.attributes.get("current_activity") == "Play Music"

    # send new activity command, with activity id
    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_REMOTE, ATTR_ACTIVITY: ACTIVITIES_TO_IDS["Watch TV"]},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_REMOTE)
    assert state.state == STATE_ON
    assert state.attributes.get("current_activity") == "Watch TV"


async def test_async_send_command(mock_hc, harmony_client, hass, mock_write_config):
    """Ensure calls to send remote commands properly propagate to devices."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.0.2.0", CONF_NAME: HUB_NAME}
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    send_commands_mock = harmony_client.send_commands

    # No device provided
    await _send_commands_and_wait(
        hass, {ATTR_ENTITY_ID: ENTITY_REMOTE, ATTR_COMMAND: PLAY_COMMAND}
    )
    send_commands_mock.assert_not_awaited()

    # Tell the TV to play by id
    await _send_commands_and_wait(
        hass,
        {
            ATTR_ENTITY_ID: ENTITY_REMOTE,
            ATTR_COMMAND: PLAY_COMMAND,
            ATTR_DEVICE: TV_DEVICE_ID,
        },
    )

    send_commands_mock.assert_awaited_once_with(
        [
            SendCommandDevice(
                device=str(TV_DEVICE_ID),
                command=PLAY_COMMAND,
                delay=float(DEFAULT_HOLD_SECS),
            ),
            DEFAULT_DELAY_SECS,
        ]
    )
    send_commands_mock.reset_mock()

    # Tell the TV to play by name
    await _send_commands_and_wait(
        hass,
        {
            ATTR_ENTITY_ID: ENTITY_REMOTE,
            ATTR_COMMAND: PLAY_COMMAND,
            ATTR_DEVICE: TV_DEVICE_NAME,
        },
    )

    send_commands_mock.assert_awaited_once_with(
        [
            SendCommandDevice(
                device=TV_DEVICE_ID,
                command=PLAY_COMMAND,
                delay=float(DEFAULT_HOLD_SECS),
            ),
            DEFAULT_DELAY_SECS,
        ]
    )
    send_commands_mock.reset_mock()

    # Tell the TV to play and stop by name
    await _send_commands_and_wait(
        hass,
        {
            ATTR_ENTITY_ID: ENTITY_REMOTE,
            ATTR_COMMAND: [PLAY_COMMAND, STOP_COMMAND],
            ATTR_DEVICE: TV_DEVICE_NAME,
        },
    )

    send_commands_mock.assert_awaited_once_with(
        [
            SendCommandDevice(
                device=TV_DEVICE_ID,
                command=PLAY_COMMAND,
                delay=float(DEFAULT_HOLD_SECS),
            ),
            DEFAULT_DELAY_SECS,
            SendCommandDevice(
                device=TV_DEVICE_ID,
                command=STOP_COMMAND,
                delay=float(DEFAULT_HOLD_SECS),
            ),
            DEFAULT_DELAY_SECS,
        ]
    )
    send_commands_mock.reset_mock()

    # Tell the TV to play by name multiple times
    await _send_commands_and_wait(
        hass,
        {
            ATTR_ENTITY_ID: ENTITY_REMOTE,
            ATTR_COMMAND: PLAY_COMMAND,
            ATTR_DEVICE: TV_DEVICE_NAME,
            ATTR_NUM_REPEATS: 2,
        },
    )

    send_commands_mock.assert_awaited_once_with(
        [
            SendCommandDevice(
                device=TV_DEVICE_ID,
                command=PLAY_COMMAND,
                delay=float(DEFAULT_HOLD_SECS),
            ),
            DEFAULT_DELAY_SECS,
            SendCommandDevice(
                device=TV_DEVICE_ID,
                command=PLAY_COMMAND,
                delay=float(DEFAULT_HOLD_SECS),
            ),
            DEFAULT_DELAY_SECS,
        ]
    )
    send_commands_mock.reset_mock()

    # Send commands to an unknown device
    await _send_commands_and_wait(
        hass,
        {
            ATTR_ENTITY_ID: ENTITY_REMOTE,
            ATTR_COMMAND: PLAY_COMMAND,
            ATTR_DEVICE: "no-such-device",
        },
    )
    send_commands_mock.assert_not_awaited()
    send_commands_mock.reset_mock()


async def test_async_send_command_custom_delay(
    mock_hc, harmony_client, hass, mock_write_config
):
    """Ensure calls to send remote commands properly propagate to devices with custom delays."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.0",
            CONF_NAME: HUB_NAME,
            ATTR_DELAY_SECS: DEFAULT_DELAY_SECS + 2,
        },
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    send_commands_mock = harmony_client.send_commands

    # Tell the TV to play by id
    await _send_commands_and_wait(
        hass,
        {
            ATTR_ENTITY_ID: ENTITY_REMOTE,
            ATTR_COMMAND: PLAY_COMMAND,
            ATTR_DEVICE: TV_DEVICE_ID,
        },
    )

    send_commands_mock.assert_awaited_once_with(
        [
            SendCommandDevice(
                device=str(TV_DEVICE_ID),
                command=PLAY_COMMAND,
                delay=float(DEFAULT_HOLD_SECS),
            ),
            DEFAULT_DELAY_SECS + 2,
        ]
    )
    send_commands_mock.reset_mock()


async def test_change_channel(mock_hc, harmony_client, hass, mock_write_config):
    """Test change channel commands."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.0.2.0", CONF_NAME: HUB_NAME}
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    change_channel_mock = harmony_client.change_channel

    # Tell the remote to change channels
    await hass.services.async_call(
        DOMAIN,
        SERVICE_CHANGE_CHANNEL,
        {ATTR_ENTITY_ID: ENTITY_REMOTE, ATTR_CHANNEL: 100},
        blocking=True,
    )
    await hass.async_block_till_done()

    change_channel_mock.assert_awaited_once_with(100)


async def test_sync(mock_hc, harmony_client, mock_write_config, hass):
    """Test the sync command."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.0.2.0", CONF_NAME: HUB_NAME}
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    sync_mock = harmony_client.sync

    # Tell the remote to change channels
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SYNC,
        {ATTR_ENTITY_ID: ENTITY_REMOTE},
        blocking=True,
    )
    await hass.async_block_till_done()

    sync_mock.assert_awaited_once()
    mock_write_config.assert_called()


async def _send_commands_and_wait(hass, service_data):
    await hass.services.async_call(
        REMOTE_DOMAIN,
        SERVICE_SEND_COMMAND,
        service_data,
        blocking=True,
    )
    await hass.async_block_till_done()
