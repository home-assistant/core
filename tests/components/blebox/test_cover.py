"""BleBox cover entities tests."""

from asynctest import CoroutineMock
import blebox_uniapi
import pytest

from homeassistant.components.blebox import cover
from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_SHUTTER,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    SUPPORT_STOP,
)

from .conftest import DefaultBoxTest, mock_feature


class CoverTest(DefaultBoxTest):
    """Shared test helpers for Cover tests."""

    HASS_TYPE = cover

    def assert_state(self, entity, state):
        """Assert that cover state is correct."""
        assert entity.state == state

        opening, closing, closed = {
            None: [None, None, None],
            STATE_OPEN: [False, False, False],
            STATE_OPENING: [True, False, False],
            STATE_CLOSING: [False, True, False],
            STATE_CLOSED: [False, False, True],
        }[state]

        assert entity.is_opening is opening
        assert entity.is_closing is closing
        assert entity.is_closed is closed

    def updateable_feature_mock(self):
        """Return an mocked feature which can be updated."""
        feature_mock = self._feature_mock

        def update():
            feature_mock.current = 78
            feature_mock.state = 2  # manually stopped

        feature_mock.async_update = CoroutineMock(side_effect=update)
        return feature_mock

    def closed_to_opening_feature_mock(self):
        """Return an mocked feature which can be updated and opened."""
        feature_mock = self._feature_mock

        def update():
            feature_mock.state = 3  # manually stopped

        def open():
            feature_mock.state = 1  # opening

        feature_mock.async_update = CoroutineMock(side_effect=update)
        feature_mock.async_open = CoroutineMock(side_effect=open)
        return feature_mock

    def open_to_closing_feature_state(self):
        """Return an mocked feature which can be updated and closed."""
        feature_mock = self._feature_mock

        def update():
            feature_mock.state = 4  # open

        def close():
            feature_mock.state = 0  # closing

        feature_mock.async_update = CoroutineMock(side_effect=update)
        feature_mock.async_close = CoroutineMock(side_effect=close)
        return feature_mock

    def closed_to_position_almost_closed_feature_mock(self):
        """Return an mocked feature which can be updated and controlled."""
        feature_mock = self._feature_mock

        def update():
            feature_mock.state = 3  # closed

        def set_position(position):
            assert position == 99  # inverted
            feature_mock.state = 1  # opening
            # feature_mock.current = position

        feature_mock.async_update = CoroutineMock(side_effect=update)
        feature_mock.async_set_position = CoroutineMock(side_effect=set_position)
        return feature_mock

    def opening_to_stop_feature_mock(self):
        """Return an mocked feature which can be updated and stopped."""
        feature_mock = self._feature_mock

        def update():
            feature_mock.state = 1  # opening

        def stop():
            feature_mock.state = 2  # manually stopped

        feature_mock.async_update = CoroutineMock(side_effect=update)
        feature_mock.async_stop = CoroutineMock(side_effect=stop)
        return feature_mock

    async def test_open(self, hass):
        """Test cover opening."""

        self.closed_to_opening_feature_mock()

        entity = await self.async_updated_entity(hass, 0)

        self.assert_state(entity, STATE_CLOSED)
        await entity.async_open_cover()
        self.assert_state(entity, STATE_OPENING)

    async def test_close(self, hass):
        """Test cover closing."""
        self.open_to_closing_feature_state()

        entity = await self.async_updated_entity(hass, 0)

        self.assert_state(entity, STATE_OPEN)
        await entity.async_close_cover()
        self.assert_state(entity, STATE_CLOSING)

    async def test_stop(self, hass):
        """Test cover stopping."""
        self.opening_to_stop_feature_mock()

        entity = await self.async_updated_entity(hass, 0)

        self.assert_state(entity, STATE_OPENING)
        await entity.async_stop_cover()
        self.assert_state(entity, STATE_OPEN)


class TestShutter(CoverTest):
    """Tests for cover devices representing a BleBox ShutterBox."""

    @pytest.fixture(autouse=True)
    def feature_mock(self):
        """Return a mocked Cover feature representing a shutterBox."""
        self._feature_mock = mock_feature(
            "covers",
            blebox_uniapi.feature.Cover,
            unique_id="BleBox-shutterBox-2bee34e750b8-position",
            full_name="shutterBox-position",
            device_class="shutter",
            current=None,
            state=None,
            has_stop=True,
            is_slider=True,
        )
        return self._feature_mock

    async def test_init(self, hass):
        """Test cover default state."""

        entity = (await self.async_entities(hass))[0]

        assert entity.name == "shutterBox-position"
        assert entity.unique_id == "BleBox-shutterBox-2bee34e750b8-position"

        assert entity.device_class == DEVICE_CLASS_SHUTTER

        assert entity.supported_features & SUPPORT_OPEN
        assert entity.supported_features & SUPPORT_CLOSE
        assert entity.supported_features & SUPPORT_STOP

        assert entity.supported_features & SUPPORT_SET_POSITION
        assert entity.current_cover_position is None

        self.assert_state(entity, None)

    async def test_update(self, hass):
        """Test cover updating."""

        self.updateable_feature_mock()

        entity = await self.async_updated_entity(hass, 0)

        assert entity.current_cover_position == 22  # 100 - 78
        self.assert_state(entity, STATE_OPEN)

    async def test_set_position(self, hass):
        """Test cover position setting."""
        self.closed_to_position_almost_closed_feature_mock()

        entity = await self.async_updated_entity(hass, 0)

        self.assert_state(entity, STATE_CLOSED)
        await entity.async_set_cover_position(**{ATTR_POSITION: 1})  # almost closed
        self.assert_state(entity, STATE_OPENING)


class TestGateBox(CoverTest):
    """Tests for cover devices representing a BleBox gateBox."""

    @pytest.fixture(autouse=True)
    def feature_mock(self):
        """Return a mocked Cover feature representing a gateBox."""
        self._feature_mock = mock_feature(
            "covers",
            blebox_uniapi.feature.Cover,
            unique_id="BleBox-gateBox-1afe34db9437-position",
            device_class="gatebox",
            full_name="gateBox-position",
            current=None,
            state=None,
            has_stop=False,
            is_slider=False,
        )
        return self._feature_mock

    def updateable_feature_mock(self):
        """Set up a mocked feature that can be updated."""
        feature_mock = self._feature_mock

        def update():
            feature_mock.current = 50
            feature_mock.state = 2  # manually stopped

        feature_mock.async_update = CoroutineMock(side_effect=update)
        return feature_mock

    async def test_init(self, hass):
        """Test cover default state."""

        entity = (await self.async_entities(hass))[0]

        assert entity.name == "gateBox-position"
        assert entity.unique_id == "BleBox-gateBox-1afe34db9437-position"
        assert entity.device_class == DEVICE_CLASS_DOOR
        assert entity.supported_features & SUPPORT_OPEN
        assert entity.supported_features & SUPPORT_CLOSE

        # Not available during init since requires fetching state to detect
        assert not entity.supported_features & SUPPORT_STOP

        assert not entity.supported_features & SUPPORT_SET_POSITION
        assert entity.current_cover_position is None
        self.assert_state(entity, None)

    async def test_update(self, hass, aioclient_mock):
        """Test cover updating."""

        self.updateable_feature_mock()

        entity = await self.async_updated_entity(hass, 0)
        assert entity.current_cover_position == 50  # 100 - 50
        self.assert_state(entity, STATE_OPEN)

    async def test_with_stop(self, hass, aioclient_mock):
        """Test stop capability is available."""

        self.opening_to_stop_feature_mock()
        feature_mock = self._feature_mock
        feature_mock.has_stop = True

        entity = await self.async_updated_entity(hass, 0)
        assert entity.supported_features & SUPPORT_STOP

    async def test_with_no_stop(self, hass, aioclient_mock):
        """Test stop capability is not available."""

        self.opening_to_stop_feature_mock()
        feature_mock = self._feature_mock
        feature_mock.has_stop = False

        entity = await self.async_updated_entity(hass, 0)
        assert not entity.supported_features & SUPPORT_STOP


class TestGateController(CoverTest):
    """Tests for cover devices representing a BleBox gateController."""

    @pytest.fixture(autouse=True)
    def feature_mock(self):
        """Return a mocked Cover feature representing a gateController."""
        self._feature_mock = mock_feature(
            "covers",
            blebox_uniapi.feature.Cover,
            unique_id="BleBox-gateController-2bee34e750b8-position",
            full_name="gateController-position",
            device_class="gate",
            current=None,
            state=None,
            has_stop=True,
            is_slider=True,
        )
        return self._feature_mock

    async def test_init(self, hass):
        """Test cover default state."""

        entity = (await self.async_entities(hass))[0]

        assert entity.name == "gateController-position"
        assert entity.unique_id == "BleBox-gateController-2bee34e750b8-position"

        assert entity.device_class == DEVICE_CLASS_DOOR

        assert entity.supported_features & SUPPORT_OPEN
        assert entity.supported_features & SUPPORT_CLOSE
        assert entity.supported_features & SUPPORT_STOP

        assert entity.supported_features & SUPPORT_SET_POSITION
        assert entity.current_cover_position is None
        self.assert_state(entity, None)

    def updateable_feature_mock(self):  # overloaded
        """Set up a mocked feature that can be updated."""
        feature_mock = self._feature_mock

        def update():
            feature_mock.current = 29  # inverted
            feature_mock.state = 2  # manually stopped

        feature_mock.async_update = CoroutineMock(side_effect=update)
        return feature_mock

    async def test_update(self, hass, aioclient_mock):
        """Test cover updating."""

        self.updateable_feature_mock()

        entity = await self.async_updated_entity(hass, 0)

        assert entity.current_cover_position == 71  # 100 - 29
        self.assert_state(entity, STATE_OPEN)

    # TODO: common for gateController and shutter (but not gateBox)
    async def test_set_position(self, hass, aioclient_mock):
        """Test cover position setting."""

        self.closed_to_position_almost_closed_feature_mock()

        entity = await self.async_updated_entity(hass, 0)

        self.assert_state(entity, STATE_CLOSED)
        await entity.async_set_cover_position(**{ATTR_POSITION: 1})  # almost closed
        self.assert_state(entity, STATE_OPENING)
