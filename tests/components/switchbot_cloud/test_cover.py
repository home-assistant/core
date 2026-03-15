"""Test for the switchbot_cloud Cover."""

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from switchbot_api import (
    BlindTiltCommands,
    CommonCommands,
    CurtainCommands,
    Device,
    RollerShadeCommands,
)

from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.switchbot_cloud import SwitchBotAPI
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import configure_integration

from tests.common import async_fire_time_changed


async def test_cover_set_attributes_normal(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test cover set_attributes normal."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Roller Shade",
            hubDeviceId="test-hub-id",
        ),
    ]

    cover_id = "cover.cover_1"
    mock_get_status.return_value = {"slidePosition": 100, "direction": "up"}
    await configure_integration(hass)
    state = hass.states.get(cover_id)
    assert state.state == STATE_CLOSED


@pytest.mark.parametrize(
    "device_model",
    [
        "Roller Shade",
        "Blind Tilt",
    ],
)
async def test_cover_set_attributes_position_is_none(
    hass: HomeAssistant, mock_list_devices, mock_get_status, device_model
) -> None:
    """Test cover_set_attributes position is none."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType=device_model,
            hubDeviceId="test-hub-id",
        ),
    ]

    cover_id = "cover.cover_1"
    mock_get_status.side_effect = [{"direction": "up"}, {"direction": "up"}]
    await configure_integration(hass)
    state = hass.states.get(cover_id)
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "device_model",
    [
        "Roller Shade",
        "Blind Tilt",
    ],
)
async def test_cover_set_attributes_coordinator_is_none(
    hass: HomeAssistant, mock_list_devices, mock_get_status, device_model
) -> None:
    """Test cover set_attributes coordinator is none."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType=device_model,
            hubDeviceId="test-hub-id",
        ),
    ]

    cover_id = "cover.cover_1"
    mock_get_status.return_value = None
    await configure_integration(hass)
    state = hass.states.get(cover_id)
    assert state.state == STATE_UNKNOWN


async def test_curtain_features(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test curtain features."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Curtain",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.side_effect = [
        {
            "slidePosition": 95,
        },
        {
            "slidePosition": 95,
        },
        {
            "slidePosition": 95,
        },
        {
            "slidePosition": 95,
        },
        {
            "slidePosition": 95,
        },
        {
            "slidePosition": 95,
        },
        {
            "slidePosition": 95,
        },
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    cover_id = "cover.cover_1"
    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    mock_send_command.assert_called_once_with(
        "cover-id-1", CommonCommands.ON, "command", "default"
    )

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    mock_send_command.assert_called_once_with(
        "cover-id-1", CommonCommands.OFF, "command", "default"
    )

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_STOP_COVER,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    mock_send_command.assert_called_once_with(
        "cover-id-1", CurtainCommands.PAUSE, "command", "default"
    )

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {"position": 50, ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    mock_send_command.assert_called_once_with(
        "cover-id-1", CurtainCommands.SET_POSITION, "command", "0,ff,50"
    )


@pytest.mark.parametrize(
    ("slide_position", "expected_state", "expected_tilt"),
    [
        (0, STATE_CLOSED, 0),  # closed down
        (19, STATE_CLOSED, 19),
        (20, STATE_OPEN, 20),
        (50, STATE_OPEN, 50),  # horizontal/open
        (80, STATE_OPEN, 80),
        (81, STATE_CLOSED, 81),
        (100, STATE_CLOSED, 100),  # closed up
    ],
)
async def test_blind_tilt_set_attributes_states(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    slide_position: int,
    expected_state: str,
    expected_tilt: int,
) -> None:
    """Test blind tilt state and tilt position at various slidePosition values.

    slidePosition uses the physical scale: 0=closed down, 50=open, 100=closed up.
    Passed through directly as HA tilt. is_closed: position < 20 or position > 80.
    """
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Blind Tilt",
            hubDeviceId="test-hub-id",
        ),
    ]

    cover_id = "cover.cover_1"
    mock_get_status.return_value = {"slidePosition": slide_position, "direction": "up"}
    await configure_integration(hass)
    state = hass.states.get(cover_id)
    assert state.state == expected_state
    assert state.attributes.get("current_tilt_position") == expected_tilt


async def test_blind_tilt_features(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test blind_tilt features."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Blind Tilt",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.side_effect = [
        {"slidePosition": 95, "direction": "up"},
        {"slidePosition": 95, "direction": "up"},
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    cover_id = "cover.cover_1"
    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER_TILT,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    mock_send_command.assert_called_once_with(
        "cover-id-1", BlindTiltCommands.FULLY_OPEN, "command", "default"
    )

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER_TILT,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    mock_send_command.assert_called_once_with(
        "cover-id-1", BlindTiltCommands.CLOSE_UP, "command", "default"
    )

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_TILT_POSITION,
            # HA 75 = physical 75 (up half): direction "up", cmd (100-75)*2=50
            {"tilt_position": 75, ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    mock_send_command.assert_called_once_with(
        "cover-id-1", BlindTiltCommands.SET_POSITION, "command", "up;50"
    )


async def test_blind_tilt_features_close_down(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test blind tilt features close_down."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Blind Tilt",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.side_effect = [
        {"slidePosition": 25, "direction": "down"},
        {"slidePosition": 25, "direction": "down"},
        {"slidePosition": 25, "direction": "down"},
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    cover_id = "cover.cover_1"
    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER_TILT,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    mock_send_command.assert_called_once_with(
        "cover-id-1", BlindTiltCommands.CLOSE_DOWN, "command", "default"
    )

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_TILT_POSITION,
            # HA 25 = physical 25 (down half): direction "down", cmd 25*2=50
            {"tilt_position": 25, ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    mock_send_command.assert_called_once_with(
        "cover-id-1", BlindTiltCommands.SET_POSITION, "command", "down;50"
    )


async def test_roller_shade_features(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test roller shade features."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Roller Shade",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.side_effect = [
        {
            "slidePosition": 95,
        },
        {
            "slidePosition": 95,
        },
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    cover_id = "cover.cover_1"
    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    mock_send_command.assert_called_once_with(
        "cover-id-1", RollerShadeCommands.SET_POSITION, "command", 0
    )

    await configure_integration(hass)
    state = hass.states.get(cover_id)
    assert state.state == STATE_OPEN

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    mock_send_command.assert_called_once_with(
        "cover-id-1", RollerShadeCommands.SET_POSITION, "command", 100
    )

    await configure_integration(hass)
    state = hass.states.get(cover_id)
    assert state.state == STATE_OPEN

    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {"position": 50, ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    mock_send_command.assert_called_once_with(
        "cover-id-1", RollerShadeCommands.SET_POSITION, "command", 50
    )


async def test_cover_set_attributes_coordinator_is_none_for_garage_door(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test cover set_attributes coordinator is none for garage_door."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Garage Door Opener",
            hubDeviceId="test-hub-id",
        ),
    ]
    cover_id = "cover.cover_1"
    mock_get_status.return_value = None
    await configure_integration(hass)
    state = hass.states.get(cover_id)
    assert state.state == STATE_UNKNOWN


async def test_garage_door_features_close(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test garage door features close."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Garage Door Opener",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.side_effect = [
        {
            "doorStatus": 1,
        },
        {
            "doorStatus": 1,
        },
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    cover_id = "cover.cover_1"
    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    mock_send_command.assert_called_once_with(
        "cover-id-1", CommonCommands.OFF, "command", "default"
    )

    await configure_integration(hass)
    state = hass.states.get(cover_id)
    assert state.state == STATE_CLOSED


async def test_garage_door_features_open(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test garage_door features open cover."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Garage Door Opener",
            hubDeviceId="test-hub-id",
        ),
    ]

    mock_get_status.side_effect = [
        {
            "doorStatus": 0,
        },
        {
            "doorStatus": 0,
        },
    ]
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    cover_id = "cover.cover_1"
    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    mock_send_command.assert_called_once_with(
        "cover-id-1", CommonCommands.ON, "command", "default"
    )

    await configure_integration(hass)
    state = hass.states.get(cover_id)
    assert state.state == STATE_OPEN


async def test_blind_tilt_poll_stops_when_moving_false(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that polling stops and state finalizes when moving becomes False."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Blind Tilt",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.return_value = {"slidePosition": 95, "direction": "up"}
    await configure_integration(hass)

    cover_id = "cover.cover_1"
    assert hass.states.get(cover_id).state == STATE_CLOSED

    mock_get_status.side_effect = [
        {"slidePosition": 70, "moving": True, "direction": "up"},
        {"slidePosition": 50, "moving": False, "direction": "up"},
    ]
    with patch.object(SwitchBotAPI, "send_command"):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER_TILT,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )

    # First poll — still moving
    freezer.tick(10)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(cover_id).state == STATE_OPENING

    # Second poll — moving=False, finalizes as open
    freezer.tick(10)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(cover_id).state == STATE_OPEN


async def test_blind_tilt_poll_stops_when_target_zone_reached(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that polling finalizes early when position enters the target zone."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Blind Tilt",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.return_value = {"slidePosition": 50, "direction": "up"}
    await configure_integration(hass)

    cover_id = "cover.cover_1"

    # Close up — target zone >= 80; API still reports moving=True but position is in zone
    mock_get_status.side_effect = [
        {"slidePosition": 85, "moving": True, "direction": "up"},
    ]
    with patch.object(SwitchBotAPI, "send_command"):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER_TILT,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )

    freezer.tick(10)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(cover_id)
    assert state.state == STATE_CLOSED
    assert state.attributes.get("is_closing") is not True


async def test_blind_tilt_new_command_cancels_prior_poll(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a new command cancels any in-progress poll task."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Blind Tilt",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.return_value = {"slidePosition": 95, "direction": "up"}
    await configure_integration(hass)

    cover_id = "cover.cover_1"

    # First command: open — poll returns moving=True
    mock_get_status.side_effect = [
        {"slidePosition": 70, "moving": True, "direction": "up"},
        {"slidePosition": 95, "moving": False, "direction": "up"},
    ]
    with patch.object(SwitchBotAPI, "send_command"):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER_TILT,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )

    freezer.tick(10)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(cover_id).state == STATE_OPENING

    # Second command: close — cancels the open poll, starts fresh
    with patch.object(SwitchBotAPI, "send_command"):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER_TILT,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )

    assert hass.states.get(cover_id).state == STATE_CLOSING

    # Poll for close — moving=False, finalizes as closed
    freezer.tick(10)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(cover_id).state == STATE_CLOSED


async def test_blind_tilt_no_spurious_open_state_during_close(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that closing through the open zone does not produce a spurious opened state."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Blind Tilt",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.return_value = {"slidePosition": 95, "direction": "up"}
    await configure_integration(hass)

    cover_id = "cover.cover_1"
    assert hass.states.get(cover_id).state == STATE_CLOSED

    # Poll passes through position 50 (open zone) before reaching closed-down zone
    mock_get_status.side_effect = [
        {"slidePosition": 50, "moving": True, "direction": "down"},
        {"slidePosition": 5, "moving": False, "direction": "down"},
    ]
    with patch.object(SwitchBotAPI, "send_command"):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER_TILT,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )

    # Mid-travel at position 50 — command in flight, cover is actively closing
    freezer.tick(10)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(cover_id).state == STATE_CLOSING

    # Final poll — moving=False at position 5 (closed-down zone)
    freezer.tick(10)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(cover_id).state == STATE_CLOSED


async def test_blind_tilt_open_tilt_then_close_cancels_open_poll(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that open_cover_tilt uses _start_poll_task so close_cover_tilt cancels it."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Blind Tilt",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.return_value = {"slidePosition": 95, "direction": "up"}
    await configure_integration(hass)

    cover_id = "cover.cover_1"

    # Open tilt — first poll still moving; open task is tracked via _start_poll_task
    mock_get_status.side_effect = [
        {"slidePosition": 70, "moving": True, "direction": "up"},
        # This response belongs to the close poll (should not be consumed by open poll)
        {"slidePosition": 95, "moving": False, "direction": "up"},
    ]
    with patch.object(SwitchBotAPI, "send_command"):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER_TILT,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )

    freezer.tick(10)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(cover_id).state == STATE_OPENING

    # Immediately send close — _start_poll_task in open_cover_tilt means the open
    # poll task is tracked and gets cancelled here, so only one poll runs for close.
    with patch.object(SwitchBotAPI, "send_command"):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER_TILT,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )

    assert hass.states.get(cover_id).state == STATE_CLOSING

    # Close poll finalizes
    freezer.tick(10)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(cover_id).state == STATE_CLOSED


async def test_blind_tilt_intermediate_target_not_finalized_early(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that an intermediate tilt target is not finalized when only in the broad open zone."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Blind Tilt",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.return_value = {"slidePosition": 95, "direction": "up"}
    await configure_integration(hass)

    cover_id = "cover.cover_1"

    # Target is 60 (open zone); position 25 is in the open zone (20-80) but far from target.
    # With zone-based logic this would finalize early — with tolerance it should not.
    mock_get_status.side_effect = [
        {"slidePosition": 25, "moving": True, "direction": "up"},
        {"slidePosition": 60, "moving": False, "direction": "up"},
    ]
    with patch.object(SwitchBotAPI, "send_command"):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_TILT_POSITION,
            {"tilt_position": 60, ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )

    # First poll — position 25 is in open zone but not within tolerance of 60, still moving
    freezer.tick(10)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    # Should still be in-flight (opening or closing), not finalized
    assert hass.states.get(cover_id).state in (STATE_OPENING, STATE_CLOSING)

    # Second poll — position 60 matches target within tolerance, moving=False → finalize
    freezer.tick(10)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(cover_id).state == STATE_OPEN


async def test_blind_tilt_poll_handles_refresh_error(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a coordinator refresh failure during polling finalizes state gracefully."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Blind Tilt",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.return_value = {"slidePosition": 95, "direction": "up"}
    await configure_integration(hass)

    cover_id = "cover.cover_1"
    assert hass.states.get(cover_id).state == STATE_CLOSED

    with patch.object(SwitchBotAPI, "send_command"):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER_TILT,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )

    assert hass.states.get(cover_id).state == STATE_OPENING

    # Simulate a network/API error during the poll refresh
    mock_get_status.side_effect = UpdateFailed("API error")
    freezer.tick(10)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Entity should finalize (not stuck in opening) after the error
    state = hass.states.get(cover_id)
    assert state.attributes.get("is_opening") is not True
    assert state.attributes.get("is_closing") is not True


async def test_blind_tilt_close_tilt_direction_none(
    hass: HomeAssistant, mock_list_devices, mock_get_status
) -> None:
    """Test that closing blind tilt raises an error when direction is not yet known."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Blind Tilt",
            hubDeviceId="test-hub-id",
        ),
    ]
    # No direction in status — entity initializes without a known direction
    mock_get_status.return_value = {"slidePosition": 25}
    await configure_integration(hass)

    cover_id = "cover.cover_1"
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER_TILT,
            {ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("tilt_position", "expected_param"),
    [
        (0, "down;0"),
        (49, "down;98"),
        (50, "up;100"),
        (51, "up;98"),
        (100, "up;0"),
    ],
)
async def test_blind_tilt_set_tilt_position_boundaries(
    hass: HomeAssistant,
    mock_list_devices,
    mock_get_status,
    tilt_position: int,
    expected_param: str,
) -> None:
    """Test blind tilt SET_POSITION command at critical tilt position boundaries."""
    mock_list_devices.return_value = [
        Device(
            version="V1.0",
            deviceId="cover-id-1",
            deviceName="cover-1",
            deviceType="Blind Tilt",
            hubDeviceId="test-hub-id",
        ),
    ]
    mock_get_status.return_value = {"slidePosition": 25, "direction": "down"}
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    cover_id = "cover.cover_1"
    with patch.object(SwitchBotAPI, "send_command") as mock_send_command:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_TILT_POSITION,
            {"tilt_position": tilt_position, ATTR_ENTITY_ID: cover_id},
            blocking=True,
        )
    mock_send_command.assert_called_once_with(
        "cover-id-1", BlindTiltCommands.SET_POSITION, "command", expected_param
    )
