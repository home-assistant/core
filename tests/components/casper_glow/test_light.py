"""Test the Casper Glow light platform."""

from unittest.mock import AsyncMock, patch

from pycasperglow import CasperGlowError, GlowState
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.casper_glow.const import (
    DEFAULT_DIMMING_TIME_MINUTES,
    DOMAIN,
)
from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_COLOR_MODE, ColorMode
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import CASPER_GLOW_DISCOVERY_INFO, setup_integration

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "light.jar"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all light entities match the snapshot."""
    with patch("homeassistant.components.casper_glow.PLATFORMS", [Platform.LIGHT]):
        await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_turn_on(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test turning on the light."""
    with patch(
        "pycasperglow.CasperGlow.turn_on",
    ) as mock_turn_on:
        await hass.services.async_call(
            "light",
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    mock_turn_on.assert_called_once()
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


async def test_turn_off(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test turning off the light."""
    # First turn on
    with patch(
        "pycasperglow.CasperGlow.turn_on",
    ):
        await hass.services.async_call(
            "light",
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    # Then turn off
    with patch(
        "pycasperglow.CasperGlow.turn_off",
    ) as mock_turn_off:
        await hass.services.async_call(
            "light",
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    mock_turn_off.assert_called_once()
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


async def test_state_update_via_callback(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that the entity updates state when the device fires a callback."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    # Simulate device pushing a state update
    device = config_entry.runtime_data.device
    device._state = GlowState(is_on=True)
    device._fire_callbacks()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON

    # Push state off
    device._state = GlowState(is_on=False)
    device._fire_callbacks()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


async def test_color_mode(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test that the light reports BRIGHTNESS color mode."""
    # Turn on the light to verify color_mode is set
    with patch(
        "pycasperglow.CasperGlow.turn_on",
    ):
        await hass.services.async_call(
            "light",
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_COLOR_MODE) == ColorMode.BRIGHTNESS


async def test_turn_on_with_brightness(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test turning on the light with brightness."""
    with (
        patch("pycasperglow.CasperGlow.turn_on") as mock_turn_on,
        patch(
            "pycasperglow.CasperGlow.set_brightness_and_dimming_time",
            new_callable=AsyncMock,
        ) as mock_set,
    ):
        await hass.services.async_call(
            "light",
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_BRIGHTNESS: 255},
            blocking=True,
        )

    mock_turn_on.assert_called_once_with()
    mock_set.assert_called_once_with(100, DEFAULT_DIMMING_TIME_MINUTES)
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_BRIGHTNESS) == 255


@pytest.mark.parametrize(
    ("ha_brightness", "device_pct", "expected_ha_brightness"),
    [
        (1, 60, 1),
        (64, 70, 64),
        (128, 80, 128),
        (192, 90, 192),
        (255, 100, 255),
    ],
)
async def test_brightness_snap_to_nearest(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    ha_brightness: int,
    device_pct: int,
    expected_ha_brightness: int,
) -> None:
    """Test that brightness values map correctly to device percentages and back."""
    with (
        patch("pycasperglow.CasperGlow.turn_on") as mock_turn_on,
        patch(
            "pycasperglow.CasperGlow.set_brightness_and_dimming_time",
            new_callable=AsyncMock,
        ) as mock_set,
    ):
        await hass.services.async_call(
            "light",
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_BRIGHTNESS: ha_brightness},
            blocking=True,
        )

    mock_turn_on.assert_called_once_with()
    mock_set.assert_called_once_with(device_pct, DEFAULT_DIMMING_TIME_MINUTES)
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_BRIGHTNESS) == expected_ha_brightness


async def test_brightness_update_via_callback(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that brightness updates via device callback."""
    device = config_entry.runtime_data.device
    device._state = GlowState(is_on=True, brightness_level=80)
    device._fire_callbacks()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_BRIGHTNESS) == 128


async def test_turn_on_error(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that a turn on error raises HomeAssistantError without marking entity unavailable."""
    with (
        patch(
            "pycasperglow.CasperGlow.turn_on",
            side_effect=CasperGlowError("Connection failed"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            "light",
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_turn_off_error(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that a turn off error raises HomeAssistantError and leaves the light on."""
    # First turn on
    with patch(
        "pycasperglow.CasperGlow.turn_on",
    ):
        await hass.services.async_call(
            "light",
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    with (
        patch(
            "pycasperglow.CasperGlow.turn_off",
            side_effect=CasperGlowError("Connection failed"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            "light",
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


async def test_pause_error(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test that a pause error raises HomeAssistantError without marking entity unavailable."""
    with (
        patch(
            "pycasperglow.CasperGlow.pause",
            side_effect=CasperGlowError("Connection failed"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            "pause",
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_resume_error(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test that a resume error raises HomeAssistantError without marking entity unavailable."""
    with (
        patch(
            "pycasperglow.CasperGlow.resume",
            side_effect=CasperGlowError("Connection failed"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            "resume",
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_device_info(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
) -> None:
    """Test device info is correctly populated."""
    device = device_registry.async_get_device(
        connections={(dr.CONNECTION_BLUETOOTH, CASPER_GLOW_DISCOVERY_INFO.address)}
    )
    assert device is not None
    assert device.manufacturer == "Casper"
    assert device.model == "Glow"


async def test_pause_service(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the pause entity service."""
    with patch(
        "pycasperglow.CasperGlow.pause",
    ) as mock_pause:
        await hass.services.async_call(
            DOMAIN,
            "pause",
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    mock_pause.assert_called_once()


async def test_resume_service(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the resume entity service."""
    with patch(
        "pycasperglow.CasperGlow.resume",
    ) as mock_resume:
        await hass.services.async_call(
            DOMAIN,
            "resume",
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    mock_resume.assert_called_once()


async def test_state_update_via_callback_after_command_failure(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that device callbacks correctly update state even after a command failure."""
    # Fail a command — entity remains in last known state (unknown), not unavailable
    with (
        patch(
            "pycasperglow.CasperGlow.turn_on",
            side_effect=CasperGlowError("Connection failed"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            "light",
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    # Device sends a push state update — entity reflects true device state
    device = config_entry.runtime_data.device
    device._state = GlowState(is_on=True)
    device._fire_callbacks()
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


async def test_unavailable_logged_only_once(
    hass: HomeAssistant, config_entry: MockConfigEntry, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that unavailability is logged only once across multiple failures."""
    with patch(
        "pycasperglow.CasperGlow.turn_on",
        side_effect=CasperGlowError("Connection failed"),
    ):
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                "light",
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: ENTITY_ID},
                blocking=True,
            )
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                "light",
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: ENTITY_ID},
                blocking=True,
            )

    assert caplog.text.count("Device is unavailable") == 1


async def test_back_online_logged_on_recovery(
    hass: HomeAssistant, config_entry: MockConfigEntry, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that recovery is logged when the device comes back online via callback."""
    # Fail first
    with (
        patch(
            "pycasperglow.CasperGlow.turn_on",
            side_effect=CasperGlowError("Connection failed"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            "light",
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    assert "Device is unavailable" in caplog.text

    # Recover via callback
    device = config_entry.runtime_data.device
    device._state = GlowState(is_on=True)
    device._fire_callbacks()
    await hass.async_block_till_done()

    assert "Device is back online" in caplog.text


async def test_back_online_logged_after_successful_command(
    hass: HomeAssistant, config_entry: MockConfigEntry, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that recovery is logged when a command succeeds after a prior failure."""
    # Fail first to set _unavailable_logged
    with (
        patch(
            "pycasperglow.CasperGlow.turn_on",
            side_effect=CasperGlowError("Connection failed"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            "light",
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    assert "Device is unavailable" in caplog.text

    # Succeed next command — recovery should be logged immediately, not waiting for callback
    with patch("pycasperglow.CasperGlow.turn_on"):
        await hass.services.async_call(
            "light",
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    assert "Device is back online" in caplog.text


async def test_back_online_logged_after_successful_turn_off(
    hass: HomeAssistant, config_entry: MockConfigEntry, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that recovery is logged when turn_off succeeds after a prior failure."""
    # First turn on so there is something to turn off
    with patch("pycasperglow.CasperGlow.turn_on"):
        await hass.services.async_call(
            "light",
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    # Fail turn_off to set _unavailable_logged
    with (
        patch(
            "pycasperglow.CasperGlow.turn_off",
            side_effect=CasperGlowError("Connection failed"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            "light",
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    assert "Device is unavailable" in caplog.text

    # Succeed next turn_off — recovery should be logged immediately
    with patch("pycasperglow.CasperGlow.turn_off"):
        await hass.services.async_call(
            "light",
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    assert "Device is back online" in caplog.text


async def test_back_online_logged_after_successful_pause(
    hass: HomeAssistant, config_entry: MockConfigEntry, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that recovery is logged when pause succeeds after a prior failure."""
    # Fail pause to set _unavailable_logged
    with (
        patch(
            "pycasperglow.CasperGlow.pause",
            side_effect=CasperGlowError("Connection failed"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            "pause",
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    assert "Device is unavailable" in caplog.text

    # Succeed next pause — recovery should be logged immediately
    with patch("pycasperglow.CasperGlow.pause"):
        await hass.services.async_call(
            DOMAIN,
            "pause",
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    assert "Device is back online" in caplog.text


async def test_back_online_logged_after_successful_resume(
    hass: HomeAssistant, config_entry: MockConfigEntry, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that recovery is logged when resume succeeds after a prior failure."""
    # Fail resume to set _unavailable_logged
    with (
        patch(
            "pycasperglow.CasperGlow.resume",
            side_effect=CasperGlowError("Connection failed"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            "resume",
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    assert "Device is unavailable" in caplog.text

    # Succeed next resume — recovery should be logged immediately
    with patch("pycasperglow.CasperGlow.resume"):
        await hass.services.async_call(
            DOMAIN,
            "resume",
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    assert "Device is back online" in caplog.text
