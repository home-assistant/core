"""Test the zerproc lights."""
from asynctest import patch

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
)
from homeassistant.components.zerproc.light import (
    DOMAIN,
    ZerprocLight,
    async_setup_entry,
)
from homeassistant.const import EVENT_HOMEASSISTANT_STOP

from tests.async_mock import MagicMock


class MockException(Exception):
    """Mock exception class."""


class MockLight(MagicMock):
    """Mock pyzerproc light class."""

    def __init__(self, address, name=None):
        """Initialize the mock class."""
        super().__init__()
        self.address = address
        self.name = name

    def _get_child_mock(self, **kwargs):
        return MagicMock(**kwargs)


async def test_init(hass):
    """Test platform setup."""
    hass.async_add_job = MagicMock()
    discover = None

    def async_track_time_interval(hass, action, interval):
        nonlocal discover
        discover = action

    entities_added = []

    def async_add_entities(entities, update_before_add=False):
        nonlocal entities_added
        entities_added += entities

    with patch(
        "homeassistant.components.zerproc.light.async_track_time_interval",
        new=async_track_time_interval,
    ):
        await async_setup_entry(hass, None, async_add_entities)

    assert discover is not None

    mock_light_1 = MockLight("AA:BB:CC:DD:EE:FF", "LEDBlue-CCDDEEFF")
    mock_light_2 = MockLight("11:22:33:44:55:66", "LEDBlue-33445566")

    with patch(
        "homeassistant.components.zerproc.light.pyzerproc.Light", MockLight
    ), patch(
        "homeassistant.components.zerproc.light.pyzerproc.discover",
        return_value=[mock_light_1, mock_light_2],
    ):
        await discover(None)
        # Calling twice should not create duplicate entities
        await discover(None)

    assert len(entities_added) == 2
    assert entities_added[0].name == "LEDBlue-CCDDEEFF"
    assert entities_added[0].unique_id == "AA:BB:CC:DD:EE:FF"
    assert entities_added[1].name == "LEDBlue-33445566"
    assert entities_added[1].unique_id == "11:22:33:44:55:66"

    entities_added.clear()
    hass.data[DOMAIN]["light_entities"] = {}

    # Test an exception connecting to one of the lights
    mock_light_1.connect.side_effect = MockException("FOO")
    with patch(
        "homeassistant.components.zerproc.light.pyzerproc.Light", MockLight
    ), patch(
        "homeassistant.components.zerproc.light.pyzerproc.discover",
        return_value=[mock_light_1, mock_light_2],
    ), patch(
        "homeassistant.components.zerproc.light.pyzerproc.ZerprocException",
        new=MockException,
    ):
        await discover(None)

    # The second light should still have been added correctly
    assert len(entities_added) == 1
    assert entities_added[0].name == "LEDBlue-33445566"
    assert entities_added[0].unique_id == "11:22:33:44:55:66"

    entities_added.clear()
    hass.data[DOMAIN]["light_entities"] = {}

    # Test an exception during discovery
    with patch(
        "homeassistant.components.zerproc.light.pyzerproc.discover",
        side_effect=MockException("TEST"),
    ), patch(
        "homeassistant.components.zerproc.light.pyzerproc.ZerprocException",
        new=MockException,
    ):
        await discover(None)

    # Should not add entities and the exception should be captured
    assert len(entities_added) == 0


def test_light_properties(hass):
    """Test ZerprocLight class properties."""
    hass.bus.async_listen_once = MagicMock()

    light = MockLight("AA:BB:CC:DD:EE:FF", "LEDBlue-CCDDEEFF")
    entity = ZerprocLight(hass, light)

    hass.bus.async_listen_once.assert_called_with(
        EVENT_HOMEASSISTANT_STOP, entity.on_hass_shutdown
    )

    assert entity.name == "LEDBlue-CCDDEEFF"
    assert entity.unique_id == "AA:BB:CC:DD:EE:FF"
    assert entity.device_info == {
        "identifiers": {(DOMAIN, entity.unique_id)},
        "name": entity.name,
    }
    assert entity.supported_features == SUPPORT_BRIGHTNESS | SUPPORT_COLOR


def test_light_turn_on(hass):
    """Test ZerprocLight turn_on."""
    light = MockLight("AA:BB:CC:DD:EE:FF", "LEDBlue-CCDDEEFF")
    entity = ZerprocLight(hass, light)

    entity.turn_on()
    light.turn_on.assert_called()

    light.reset_mock()

    entity.turn_on(**{ATTR_BRIGHTNESS: 25})

    light.turn_on.assert_not_called()
    light.set_color.assert_called_with(25, 25, 25)

    light.reset_mock()
    entity._hs_color = (50, 50)

    entity.turn_on(**{ATTR_BRIGHTNESS: 25})

    light.turn_on.assert_not_called()
    light.set_color.assert_called_with(25, 22, 12)

    light.reset_mock()

    entity.turn_on(**{ATTR_HS_COLOR: (50, 50)})

    light.turn_on.assert_not_called()
    light.set_color.assert_called_with(255, 233, 127)

    light.reset_mock()
    entity._brightness = 75

    entity.turn_on(**{ATTR_HS_COLOR: (50, 50)})

    light.turn_on.assert_not_called()
    light.set_color.assert_called_with(75, 68, 37)

    light.reset_mock()

    entity.turn_on(**{ATTR_BRIGHTNESS: 200, ATTR_HS_COLOR: (75, 75)})

    light.turn_on.assert_not_called()
    light.set_color.assert_called_with(162, 200, 50)


def test_light_turn_off(hass):
    """Test ZerprocLight turn_off."""
    light = MockLight("AA:BB:CC:DD:EE:FF", "LEDBlue-CCDDEEFF")
    entity = ZerprocLight(hass, light)

    entity.turn_off()
    light.turn_off.assert_called()


def test_light_update(hass):
    """Test ZerprocLight update."""
    light = MockLight("AA:BB:CC:DD:EE:FF", "LEDBlue-CCDDEEFF")
    entity = ZerprocLight(hass, light)

    assert entity.available is True

    # Test an exception during discovery
    with patch(
        "homeassistant.components.zerproc.light.pyzerproc.ZerprocException",
        new=MockException,
    ):
        light.get_state.side_effect = MockException("TEST")
        entity.update()

    assert entity.available is False

    state = MagicMock()
    state.is_on = False
    state.color = (200, 128, 100)
    light.get_state.side_effect = None
    light.get_state.return_value = state

    entity.update()

    assert entity.available is True
    assert entity.brightness == 200
    assert entity.is_on is False
    assert entity.hs_color == (16.8, 50.0)

    state.is_on = True
    state.color = (175, 150, 220)
    light.get_state.side_effect = None
    light.get_state.return_value = state

    entity.update()

    assert entity.available is True
    assert entity.brightness == 220
    assert entity.is_on is True
    assert entity.hs_color == (261.429, 31.818)
