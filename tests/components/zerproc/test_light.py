"""Test the zerproc lights."""

from unittest.mock import MagicMock, patch

import pytest
import pyzerproc

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_MODE,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ATTR_XY_COLOR,
    SCAN_INTERVAL,
    ColorMode,
)
from homeassistant.components.zerproc.const import (
    DATA_ADDRESSES,
    DATA_DISCOVERY_SUBSCRIPTION,
    DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture
async def mock_entry() -> MockConfigEntry:
    """Create a mock light entity."""
    return MockConfigEntry(domain=DOMAIN)


@pytest.fixture
async def mock_light(hass: HomeAssistant, mock_entry: MockConfigEntry) -> MagicMock:
    """Create a mock light entity."""

    mock_entry.add_to_hass(hass)

    light = MagicMock(spec=pyzerproc.Light)
    light.address = "AA:BB:CC:DD:EE:FF"
    light.name = "LEDBlue-CCDDEEFF"
    light.is_connected.return_value = False

    mock_state = pyzerproc.LightState(False, (0, 0, 0))

    with (
        patch(
            "homeassistant.components.zerproc.light.pyzerproc.discover",
            return_value=[light],
        ),
        patch.object(light, "connect"),
        patch.object(light, "get_state", return_value=mock_state),
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    light.is_connected.return_value = True

    return light


async def test_init(hass: HomeAssistant, mock_entry) -> None:
    """Test platform setup."""

    mock_entry.add_to_hass(hass)

    mock_light_1 = MagicMock(spec=pyzerproc.Light)
    mock_light_1.address = "AA:BB:CC:DD:EE:FF"
    mock_light_1.name = "LEDBlue-CCDDEEFF"
    mock_light_1.is_connected.return_value = True

    mock_light_2 = MagicMock(spec=pyzerproc.Light)
    mock_light_2.address = "11:22:33:44:55:66"
    mock_light_2.name = "LEDBlue-33445566"
    mock_light_2.is_connected.return_value = True

    mock_state_1 = pyzerproc.LightState(False, (0, 0, 0))
    mock_state_2 = pyzerproc.LightState(True, (0, 80, 255))

    mock_light_1.get_state.return_value = mock_state_1
    mock_light_2.get_state.return_value = mock_state_2

    with patch(
        "homeassistant.components.zerproc.light.pyzerproc.discover",
        return_value=[mock_light_1, mock_light_2],
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("light.ledblue_ccddeeff")
    assert state.state == STATE_OFF
    assert state.attributes == {
        ATTR_FRIENDLY_NAME: "LEDBlue-CCDDEEFF",
        ATTR_SUPPORTED_COLOR_MODES: [ColorMode.HS],
        ATTR_SUPPORTED_FEATURES: 0,
        ATTR_COLOR_MODE: None,
        ATTR_BRIGHTNESS: None,
        ATTR_HS_COLOR: None,
        ATTR_RGB_COLOR: None,
        ATTR_XY_COLOR: None,
    }

    state = hass.states.get("light.ledblue_33445566")
    assert state.state == STATE_ON
    assert state.attributes == {
        ATTR_FRIENDLY_NAME: "LEDBlue-33445566",
        ATTR_SUPPORTED_COLOR_MODES: [ColorMode.HS],
        ATTR_SUPPORTED_FEATURES: 0,
        ATTR_COLOR_MODE: ColorMode.HS,
        ATTR_BRIGHTNESS: 255,
        ATTR_HS_COLOR: (221.176, 100.0),
        ATTR_RGB_COLOR: (0, 80, 255),
        ATTR_XY_COLOR: (0.138, 0.08),
    }

    with patch.object(hass.loop, "stop"):
        await hass.async_stop()

    assert mock_light_1.disconnect.called
    assert mock_light_2.disconnect.called

    assert hass.data[DOMAIN]["addresses"] == {"AA:BB:CC:DD:EE:FF", "11:22:33:44:55:66"}


async def test_discovery_exception(hass: HomeAssistant, mock_entry) -> None:
    """Test platform setup."""

    mock_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.zerproc.light.pyzerproc.discover",
        side_effect=pyzerproc.ZerprocException("TEST"),
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    # The exception should be captured and no entities should be added
    assert len(hass.data[DOMAIN]["addresses"]) == 0


async def test_remove_entry(hass: HomeAssistant, mock_light, mock_entry) -> None:
    """Test platform setup."""
    assert hass.data[DOMAIN][DATA_ADDRESSES] == {"AA:BB:CC:DD:EE:FF"}
    assert DATA_DISCOVERY_SUBSCRIPTION in hass.data[DOMAIN]

    with patch.object(mock_light, "disconnect") as mock_disconnect:
        await hass.config_entries.async_remove(mock_entry.entry_id)

    assert mock_disconnect.called
    assert DOMAIN not in hass.data


async def test_remove_entry_exceptions_caught(
    hass: HomeAssistant, mock_light, mock_entry
) -> None:
    """Assert that disconnect exceptions are caught."""
    with patch.object(
        mock_light, "disconnect", side_effect=pyzerproc.ZerprocException("Mock error")
    ) as mock_disconnect:
        await hass.config_entries.async_remove(mock_entry.entry_id)

    assert mock_disconnect.called


async def test_light_turn_on(hass: HomeAssistant, mock_light) -> None:
    """Test ZerprocLight turn_on."""
    utcnow = dt_util.utcnow()
    with patch.object(mock_light, "turn_on") as mock_turn_on:
        await hass.services.async_call(
            "light",
            "turn_on",
            {ATTR_ENTITY_ID: "light.ledblue_ccddeeff"},
            blocking=True,
        )
        await hass.async_block_till_done()
    mock_turn_on.assert_called()

    with patch.object(mock_light, "set_color") as mock_set_color:
        await hass.services.async_call(
            "light",
            "turn_on",
            {ATTR_ENTITY_ID: "light.ledblue_ccddeeff", ATTR_BRIGHTNESS: 25},
            blocking=True,
        )
        await hass.async_block_till_done()
    mock_set_color.assert_called_with(25, 25, 25)

    # Make sure no discovery calls are made while we emulate time passing
    with patch("homeassistant.components.zerproc.light.pyzerproc.discover"):
        with patch.object(
            mock_light,
            "get_state",
            return_value=pyzerproc.LightState(True, (175, 150, 220)),
        ):
            utcnow = utcnow + SCAN_INTERVAL
            async_fire_time_changed(hass, utcnow)
            await hass.async_block_till_done()

        with patch.object(mock_light, "set_color") as mock_set_color:
            await hass.services.async_call(
                "light",
                "turn_on",
                {ATTR_ENTITY_ID: "light.ledblue_ccddeeff", ATTR_BRIGHTNESS: 25},
                blocking=True,
            )
            await hass.async_block_till_done()

        mock_set_color.assert_called_with(19, 17, 25)

        with patch.object(mock_light, "set_color") as mock_set_color:
            await hass.services.async_call(
                "light",
                "turn_on",
                {ATTR_ENTITY_ID: "light.ledblue_ccddeeff", ATTR_HS_COLOR: (50, 50)},
                blocking=True,
            )
            await hass.async_block_till_done()

        mock_set_color.assert_called_with(220, 201, 110)

        with patch.object(
            mock_light,
            "get_state",
            return_value=pyzerproc.LightState(True, (75, 75, 75)),
        ):
            utcnow = utcnow + SCAN_INTERVAL
            async_fire_time_changed(hass, utcnow)
            await hass.async_block_till_done()

        with patch.object(mock_light, "set_color") as mock_set_color:
            await hass.services.async_call(
                "light",
                "turn_on",
                {ATTR_ENTITY_ID: "light.ledblue_ccddeeff", ATTR_HS_COLOR: (50, 50)},
                blocking=True,
            )
            await hass.async_block_till_done()

        mock_set_color.assert_called_with(75, 68, 37)

        with patch.object(mock_light, "set_color") as mock_set_color:
            await hass.services.async_call(
                "light",
                "turn_on",
                {
                    ATTR_ENTITY_ID: "light.ledblue_ccddeeff",
                    ATTR_BRIGHTNESS: 200,
                    ATTR_HS_COLOR: (75, 75),
                },
                blocking=True,
            )
            await hass.async_block_till_done()

        mock_set_color.assert_called_with(162, 200, 50)


async def test_light_turn_off(hass: HomeAssistant, mock_light) -> None:
    """Test ZerprocLight turn_on."""
    with patch.object(mock_light, "turn_off") as mock_turn_off:
        await hass.services.async_call(
            "light",
            "turn_off",
            {ATTR_ENTITY_ID: "light.ledblue_ccddeeff"},
            blocking=True,
        )
        await hass.async_block_till_done()
    mock_turn_off.assert_called()


async def test_light_update(hass: HomeAssistant, mock_light) -> None:
    """Test ZerprocLight update."""
    utcnow = dt_util.utcnow()

    state = hass.states.get("light.ledblue_ccddeeff")
    assert state.state == STATE_OFF
    assert state.attributes == {
        ATTR_FRIENDLY_NAME: "LEDBlue-CCDDEEFF",
        ATTR_SUPPORTED_COLOR_MODES: [ColorMode.HS],
        ATTR_SUPPORTED_FEATURES: 0,
        ATTR_COLOR_MODE: None,
        ATTR_BRIGHTNESS: None,
        ATTR_HS_COLOR: None,
        ATTR_RGB_COLOR: None,
        ATTR_XY_COLOR: None,
    }

    # Make sure no discovery calls are made while we emulate time passing
    with patch("homeassistant.components.zerproc.light.pyzerproc.discover"):
        # Test an exception during discovery
        with patch.object(
            mock_light, "get_state", side_effect=pyzerproc.ZerprocException("TEST")
        ):
            utcnow = utcnow + SCAN_INTERVAL
            async_fire_time_changed(hass, utcnow)
            await hass.async_block_till_done()

        state = hass.states.get("light.ledblue_ccddeeff")
        assert state.state == STATE_UNAVAILABLE
        assert state.attributes == {
            ATTR_FRIENDLY_NAME: "LEDBlue-CCDDEEFF",
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.HS],
            ATTR_SUPPORTED_FEATURES: 0,
        }

        with patch.object(
            mock_light,
            "get_state",
            return_value=pyzerproc.LightState(False, (200, 128, 100)),
        ):
            utcnow = utcnow + SCAN_INTERVAL
            async_fire_time_changed(hass, utcnow)
            await hass.async_block_till_done()

        state = hass.states.get("light.ledblue_ccddeeff")
        assert state.state == STATE_OFF
        assert state.attributes == {
            ATTR_FRIENDLY_NAME: "LEDBlue-CCDDEEFF",
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.HS],
            ATTR_SUPPORTED_FEATURES: 0,
            ATTR_COLOR_MODE: None,
            ATTR_BRIGHTNESS: None,
            ATTR_HS_COLOR: None,
            ATTR_RGB_COLOR: None,
            ATTR_XY_COLOR: None,
        }

        with patch.object(
            mock_light,
            "get_state",
            return_value=pyzerproc.LightState(True, (175, 150, 220)),
        ):
            utcnow = utcnow + SCAN_INTERVAL
            async_fire_time_changed(hass, utcnow)
            await hass.async_block_till_done()

        state = hass.states.get("light.ledblue_ccddeeff")
        assert state.state == STATE_ON
        assert state.attributes == {
            ATTR_FRIENDLY_NAME: "LEDBlue-CCDDEEFF",
            ATTR_SUPPORTED_COLOR_MODES: [ColorMode.HS],
            ATTR_SUPPORTED_FEATURES: 0,
            ATTR_COLOR_MODE: ColorMode.HS,
            ATTR_BRIGHTNESS: 220,
            ATTR_HS_COLOR: (261.429, 31.818),
            ATTR_RGB_COLOR: (202, 173, 255),
            ATTR_XY_COLOR: (0.291, 0.232),
        }
