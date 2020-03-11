"""BleBox light entities tests."""

from asynctest import CoroutineMock
import blebox_uniapi
import pytest

from homeassistant.components.blebox import light
from homeassistant.components.light import (
    ATTR_HS_COLOR,
    ATTR_WHITE_VALUE,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_WHITE_VALUE,
)
from homeassistant.util import color

from .conftest import DefaultBoxTest, mock_feature


class LightTest(DefaultBoxTest):
    """Shared test helpers for Light tests."""

    HASS_TYPE = light


class TestDimmer(LightTest):
    """Tests for BleBox dimmerBox."""

    @pytest.fixture(autouse=True)
    def feature_mock(self):
        """Return a mocked Light feature representing a dimmerBox."""
        self._feature_mock = mock_feature(
            "lights",
            blebox_uniapi.feature.Light,
            unique_id="BleBox-dimmerBox-1afe34e750b8-brightness",
            full_name="dimmerBox-brightness",
            device_class=None,
            brightness=65,
            is_on=True,
        )
        return self._feature_mock

    def updateable_feature_mock(self):
        """Set up mocked feature that can be updated."""
        feature_mock = self._feature_mock

        def update():
            feature_mock.brightness = 53

        feature_mock.async_update = CoroutineMock(side_effect=update)
        return feature_mock

    async def test_init(self, hass):
        """Test cover default state."""
        entity = (await self.async_entities(hass))[0]

        assert entity.name == "dimmerBox-brightness"
        assert entity.unique_id == "BleBox-dimmerBox-1afe34e750b8-brightness"

        assert entity.supported_features & SUPPORT_BRIGHTNESS
        assert entity.brightness == 65

        assert entity.is_on is True

    async def test_update(self, hass, aioclient_mock):
        """Test light updating."""

        self.updateable_feature_mock()

        entity = await self.async_updated_entity(hass, 0)

        assert entity.brightness == 53
        assert entity.is_on is True

    def off_to_on_feature_state(self):
        """Set up mocked feature that can be updated and turned on."""
        feature_mock = self._feature_mock

        def update():
            feature_mock.is_on = False
            feature_mock.brightness = 0  # off
            feature_mock.sensible_on_value = 254

        def turn_on(brightness):
            assert brightness == 254
            feature_mock.brightness = 254  # on
            feature_mock.is_on = True  # on

        feature_mock.async_update = CoroutineMock(side_effect=update)
        feature_mock.async_on = CoroutineMock(side_effect=turn_on)
        return feature_mock

    def off_to_on_via_brightness_feature_state(self):
        """Set up mocked feature that can be updated and controlled."""
        feature_mock = self._feature_mock

        def update():
            feature_mock.is_on = False
            feature_mock.brightness = 0  # off
            feature_mock.sensible_on_value = 254

            def apply(value, brightness):
                assert value == 254
                return brightness

            feature_mock.apply_brightness = apply

        def turn_on(brightness):
            assert brightness == 202
            feature_mock.brightness = 202  # on
            feature_mock.is_on = True  # on

        feature_mock.async_update = CoroutineMock(side_effect=update)
        feature_mock.async_on = CoroutineMock(side_effect=turn_on)
        return feature_mock

    async def test_on(self, hass, aioclient_mock):
        """Test light on."""

        self.off_to_on_feature_state()

        entity = await self.async_updated_entity(hass, 0)
        assert entity.is_on is False

        await entity.async_turn_on()

        assert entity.is_on is True
        assert entity.brightness == 254

    async def test_on_with_brightness(self, hass, aioclient_mock):
        """Test light on with a brightness value."""

        self.off_to_on_via_brightness_feature_state()

        entity = await self.async_updated_entity(hass, 0)
        assert entity.is_on is False

        await entity.async_turn_on(brightness=202)

        assert entity.is_on is True
        assert entity.brightness == 202  # as if desired brightness not reached yet

    def on_to_off_feature_mock(self):
        """Set up mocked feature that can be updated and turned off."""
        feature_mock = self._feature_mock

        def update():
            feature_mock.is_on = True

        def turn_off():
            feature_mock.is_on = False
            feature_mock.brightness = 0  # off

        feature_mock.async_update = CoroutineMock(side_effect=update)
        feature_mock.async_off = CoroutineMock(side_effect=turn_off)
        return feature_mock

    async def test_off(self, hass, aioclient_mock):
        """Test light off."""

        self.on_to_off_feature_mock()

        entity = await self.async_updated_entity(hass, 0)
        assert entity.is_on is True

        await entity.async_turn_off()

        assert entity.is_on is False
        assert entity.brightness == 0


class TestWLightBoxS(LightTest):
    """Tests for BleBox wLightBoxS."""

    @pytest.fixture(autouse=True)
    def feature_mock(self):
        """Return a mocked Light feature representing a wLightBoxS."""
        self._feature_mock = mock_feature(
            "lights",
            blebox_uniapi.feature.Light,
            unique_id="BleBox-wLightBoxS-1afe34e750b8-color",
            full_name="wLightBoxS-color",
            device_class=None,
            supports_white=False,
            brightness=0xE3,
            is_on=True,
        )
        return self._feature_mock

    async def test_init(self, hass):
        """Test cover default state."""
        entity = (await self.async_entities(hass))[0]

        assert entity.name == "wLightBoxS-color"
        assert entity.unique_id == "BleBox-wLightBoxS-1afe34e750b8-color"

        assert entity.supported_features & SUPPORT_BRIGHTNESS
        assert entity.brightness == 0xE3

        assert entity.is_on is True  # state already available

    def updateable_feature_mock(self):
        """Set up mocked feature that can be updated."""
        feature_mock = self._feature_mock

        def update():
            feature_mock.brightness = 0xAB
            feature_mock.is_on = True

        feature_mock.async_update = CoroutineMock(side_effect=update)
        return feature_mock

    async def test_update(self, hass):
        """Test light updating."""

        self.updateable_feature_mock()

        entity = await self.async_updated_entity(hass, 0)

        assert entity.brightness == 0xAB
        assert entity.is_on is True

    def off_to_on_feature_state(self):
        """Set up mocked feature that can be updated and turned on."""
        feature_mock = self._feature_mock

        def update():
            feature_mock.is_on = False
            feature_mock.sensible_on_value = 254

        def turn_on(brightness):
            assert brightness == 254
            feature_mock.brightness = 254  # on
            feature_mock.is_on = True  # on

        feature_mock.async_update = CoroutineMock(side_effect=update)
        feature_mock.async_on = CoroutineMock(side_effect=turn_on)
        return feature_mock

    async def test_on(self, hass, aioclient_mock):
        """Test light on."""
        self.off_to_on_feature_state()

        entity = await self.async_updated_entity(hass, 0)
        assert entity.is_on is False

        await entity.async_turn_on()
        assert entity.is_on is True
        assert entity.brightness == 254


class TestWLightBox(LightTest):
    """Tests for BleBox wLightBox."""

    @pytest.fixture(autouse=True)
    def feature_mock(self):
        """Return a mocked Light feature representing a wLightBox."""
        self._feature_mock = mock_feature(
            "lights",
            blebox_uniapi.feature.Light,
            unique_id="BleBox-wLightBox-1afe34e750b8-color",
            full_name="wLightBox-color",
            device_class=None,
            is_on=True,
            white_value=0xD9,
            rgbw_hex="abcdefd9",
        )
        return self._feature_mock

    async def test_init(self, hass):
        """Test cover default state."""
        entity = (await self.async_entities(hass))[0]

        assert entity.name == "wLightBox-color"
        assert entity.unique_id == "BleBox-wLightBox-1afe34e750b8-color"

        assert entity.supported_features & SUPPORT_WHITE_VALUE
        assert entity.white_value == 0xD9

        assert entity.supported_features & SUPPORT_COLOR
        assert entity.hs_color == (210.0, 28.452)
        assert entity.white_value == 0xD9

        assert entity.is_on is True  # state already available

    def updateable_feature_mock(self):  # overloaded
        """Set up mocked feature that can be updated."""
        feature_mock = self._feature_mock

        def update():
            feature_mock.rgbw_hex = "fa00203A"
            feature_mock.white_value = 0x3A

        feature_mock.async_update = CoroutineMock(side_effect=update)
        return feature_mock

    async def test_update(self, hass, aioclient_mock):
        """Test light updating."""

        self.updateable_feature_mock()

        entity = await self.async_updated_entity(hass, 0)
        assert entity.hs_color == (352.32, 100.0)
        assert entity.white_value == 0x3A
        assert entity.is_on is True  # state already available

    def on_via_just_white_feature_mock(self):
        """Set up mocked feature that can be updated and turned on."""
        feature_mock = self._feature_mock

        def apply_white(value, white):
            assert value == "f1e2d305"
            assert white == 0xC7
            return "f1e2d3c7"

        feature_mock.apply_white = apply_white
        feature_mock.sensible_on_value = "f1e2d305"

        def update():
            feature_mock.is_on = False

        def turn_on(value):
            feature_mock.is_on = True
            assert value == "f1e2d3c7"
            feature_mock.white_value = 0xC7  # on
            feature_mock.rgbw_hex = "f1e2d3c7"

        feature_mock.async_update = CoroutineMock(side_effect=update)
        feature_mock.async_on = CoroutineMock(side_effect=turn_on)
        return feature_mock

    async def test_on_via_just_whiteness(self, hass):
        """Test light on."""

        self.on_via_just_white_feature_mock()

        entity = await self.async_updated_entity(hass, 0)
        assert entity.is_on is False

        await entity.async_turn_on(**{ATTR_WHITE_VALUE: 0xC7})

        assert entity.is_on is True
        assert entity.white_value == 0xC7
        assert entity.hs_color == color.color_RGB_to_hs(0xF1, 0xE2, 0xD3)

    def on_via_reset_white_feature_mock(self):
        """Set up mocked feature that can be updated and turned on."""
        feature_mock = self._feature_mock

        def apply_white(value, white):
            assert value == "f1e2d305"
            assert white == 0x0
            return "f1e2d300"

        feature_mock.apply_white = apply_white
        feature_mock.sensible_on_value = "f1e2d305"

        def update():
            feature_mock.is_on = False

        def turn_on(value):
            feature_mock.is_on = True
            feature_mock.white_value = 0x0
            assert value == "f1e2d300"
            feature_mock.rgbw_hex = "f1e2d300"

        feature_mock.async_update = CoroutineMock(side_effect=update)
        feature_mock.async_on = CoroutineMock(side_effect=turn_on)
        return feature_mock

    async def test_on_via_reset_whiteness(self, hass, aioclient_mock):
        """Test light on."""

        self.on_via_reset_white_feature_mock()

        entity = await self.async_updated_entity(hass, 0)
        assert entity.is_on is False

        await entity.async_turn_on(**{ATTR_WHITE_VALUE: 0x0})

        assert entity.is_on is True
        assert entity.white_value == 0x0
        assert entity.hs_color == color.color_RGB_to_hs(0xF1, 0xE2, 0xD3)

    def on_via_hsl_feature_mock(self):
        """Set up mocked feature that can be updated and turned on."""
        feature_mock = self._feature_mock

        def apply_color(value, color):
            assert value == "c1a2e3e4"
            assert color == "ffa0b1"
            return "ffa1b2e4"

        feature_mock.apply_color = apply_color
        feature_mock.sensible_on_value = "c1a2e3e4"

        def update():
            feature_mock.is_on = False
            feature_mock.rgbw_hex = "00000000"

        def turn_on(value):
            feature_mock.is_on = True
            assert value == "ffa1b2e4"
            feature_mock.white_value = 0xE4
            feature_mock.rgbw_hex = value

        feature_mock.async_update = CoroutineMock(side_effect=update)
        feature_mock.async_on = CoroutineMock(side_effect=turn_on)
        return feature_mock

    async def test_on_via_just_hsl_color(self, hass, aioclient_mock):
        """Test light on."""

        self.on_via_hsl_feature_mock()

        entity = await self.async_updated_entity(hass, 0)
        assert entity.is_on is False

        input_rgb = (0xFF, 0xA1, 0xB2)
        hs_color = color.color_RGB_to_hs(*input_rgb)

        await entity.async_turn_on(**{ATTR_HS_COLOR: hs_color})

        assert entity.is_on is True

        # expected RGB is "ffa0b1e4" - rounded RGB + white is from last color
        assert entity.hs_color == color.color_RGB_to_hs(*input_rgb)
        assert entity.white_value == 0xE4

    def on_with_last_color_feature_mock(self):
        """Set up mocked feature that can be updated and turned on."""
        feature_mock = self._feature_mock

        feature_mock.sensible_on_value = "f1e2d3e4"

        def update():
            feature_mock.is_on = False

        def turn_on(value):
            feature_mock.is_on = True
            assert value == "f1e2d3e4"
            feature_mock.white_value = 0xE4
            feature_mock.rgbw_hex = value

        feature_mock.async_update = CoroutineMock(side_effect=update)
        feature_mock.async_on = CoroutineMock(side_effect=turn_on)
        return feature_mock

    async def test_on_to_last_color(self, hass, aioclient_mock):
        """Test light on."""

        self.on_with_last_color_feature_mock()

        entity = await self.async_updated_entity(hass, 0)
        assert entity.is_on is False

        await entity.async_turn_on()

        assert entity.is_on is True
        assert entity.white_value == 0xE4
        assert entity.hs_color == color.color_RGB_to_hs(0xF1, 0xE2, 0xD3)

    def off_feature_mock(self):
        """Set up mocked feature that can be updated and turned off."""
        feature_mock = self._feature_mock

        def update():
            feature_mock.is_on = True

        def turn_off():
            feature_mock.is_on = False
            feature_mock.white_value = 0x0
            feature_mock.rgbw_hex = "00000000"

        feature_mock.async_update = CoroutineMock(side_effect=update)
        feature_mock.async_off = CoroutineMock(side_effect=turn_off)
        return feature_mock

    async def test_off(self, hass, aioclient_mock):
        """Test light off."""

        self.off_feature_mock()

        entity = await self.async_updated_entity(hass, 0)
        assert entity.is_on is True

        await entity.async_turn_off()

        assert entity.is_on is False
        assert entity.hs_color == (0, 0)
        assert entity.white_value == 0x00
