"""BleBox cover entities tests."""

from asynctest import CoroutineMock, PropertyMock, call, patch
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


class CoverTestData(DefaultBoxTest):
    """Shared test helpers for Cover tests."""

    HASS_TYPE = cover

    def __init__(self, mock):
        """Set the mock object."""
        self._feature_mock = mock

    def default_mock(self):
        """Implement method needed by shared tests."""
        return self._feature_mock


def shutterbox_data():
    """Return a default cover entity mock."""
    feature = mock_feature(
        "covers",
        blebox_uniapi.cover.Cover,
        unique_id="BleBox-shutterBox-2bee34e750b8-position",
        full_name="shutterBox-position",
        device_class="shutter",
        current=None,
        state=None,
        has_stop=True,
        is_slider=True,
    )
    product = feature.product
    type(product).name = PropertyMock(return_value="My shutter")
    type(product).model = PropertyMock(return_value="shutterBox")
    return CoverTestData(feature)


def gatebox_data():
    """Return a default gatebox cover entity mock."""
    feature = mock_feature(
        "covers",
        blebox_uniapi.cover.Cover,
        unique_id="BleBox-gateBox-1afe34db9437-position",
        device_class="gatebox",
        full_name="gateBox-position",
        current=None,
        state=None,
        has_stop=False,
        is_slider=False,
    )
    product = feature.product
    type(product).name = PropertyMock(return_value="My gatebox")
    type(product).model = PropertyMock(return_value="gateBox")
    return CoverTestData(feature)


def gatecontroller_data():
    """Return a default gateController cover entity mock."""
    feature = mock_feature(
        "covers",
        blebox_uniapi.cover.Cover,
        unique_id="BleBox-gateController-2bee34e750b8-position",
        full_name="gateController-position",
        device_class="gate",
        current=None,
        state=None,
        has_stop=True,
        is_slider=True,
    )
    product = feature.product
    type(product).name = PropertyMock(return_value="My gate controller")
    type(product).model = PropertyMock(return_value="gateController")
    return CoverTestData(feature)


@pytest.fixture
def shutterbox():
    """Return a shutterBox fixture."""
    return shutterbox_data()


@pytest.fixture
def gatebox():
    """Return a gateBox fixture."""
    return gatebox_data()


@pytest.fixture
def gatecontroller():
    """Return a gateController fixture."""
    return gatecontroller_data()


@pytest.fixture(params=[gatecontroller_data, gatebox_data, shutterbox_data])
def all_types(request):
    """Return a fixture using all cover types."""
    return request.param()


@pytest.fixture(params=[gatecontroller_data, shutterbox_data])
def all_sliders(request):
    """Return a fixture using all positionable types."""
    return request.param()


@pytest.fixture(params=[gatebox_data])
def not_sliders(request):
    """Return a fixture using all non-positionable types."""
    return request.param()


def assert_state(entity, state):
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


async def test_init_gatecontroller(gatecontroller, hass):
    """Test gateController default state."""

    data = gatecontroller
    entity = (await data.async_mock_entities(hass))[0]

    assert entity.name == "gateController-position"
    assert entity.unique_id == "BleBox-gateController-2bee34e750b8-position"

    assert entity.device_class == DEVICE_CLASS_DOOR

    assert entity.supported_features & SUPPORT_OPEN
    assert entity.supported_features & SUPPORT_CLOSE
    assert entity.supported_features & SUPPORT_STOP

    assert entity.supported_features & SUPPORT_SET_POSITION
    assert entity.current_cover_position is None
    assert_state(entity, None)


async def test_init_shutterbox(shutterbox, hass):
    """Test gateBox default state."""

    data = shutterbox
    entity = (await data.async_mock_entities(hass))[0]

    assert entity.name == "shutterBox-position"
    assert entity.unique_id == "BleBox-shutterBox-2bee34e750b8-position"

    assert entity.device_class == DEVICE_CLASS_SHUTTER

    assert entity.supported_features & SUPPORT_OPEN
    assert entity.supported_features & SUPPORT_CLOSE
    assert entity.supported_features & SUPPORT_STOP

    assert entity.supported_features & SUPPORT_SET_POSITION
    assert entity.current_cover_position is None

    assert_state(entity, None)


async def test_init_gatebox(gatebox, hass):
    """Test cover default state."""

    data = gatebox
    entity = (await data.async_mock_entities(hass))[0]

    assert entity.name == "gateBox-position"
    assert entity.unique_id == "BleBox-gateBox-1afe34db9437-position"
    assert entity.device_class == DEVICE_CLASS_DOOR
    assert entity.supported_features & SUPPORT_OPEN
    assert entity.supported_features & SUPPORT_CLOSE

    # Not available during init since requires fetching state to detect
    assert not entity.supported_features & SUPPORT_STOP

    assert not entity.supported_features & SUPPORT_SET_POSITION
    assert entity.current_cover_position is None
    assert_state(entity, None)


async def test_shutterbox_device_info(shutterbox, hass):
    """Test device info."""

    data = shutterbox
    entity = (await data.async_mock_entities(hass))[0]
    info = entity.device_info
    assert info["name"] == "My shutter"
    assert info["identifiers"] == {("blebox", "abcd0123ef5678")}
    assert info["manufacturer"] == "BleBox"
    assert info["model"] == "shutterBox"
    assert info["sw_version"] == "1.23"


async def test_gatebox_device_info(gatebox, hass):
    """Test device info."""

    data = gatebox
    entity = (await data.async_mock_entities(hass))[0]
    info = entity.device_info
    assert info["name"] == "My gatebox"
    assert info["identifiers"] == {("blebox", "abcd0123ef5678")}
    assert info["manufacturer"] == "BleBox"
    assert info["model"] == "gateBox"
    assert info["sw_version"] == "1.23"


async def test_gate_device_info(gatecontroller, hass):
    """Test device info."""

    data = gatecontroller
    entity = (await data.async_mock_entities(hass))[0]
    info = entity.device_info
    assert info["name"] == "My gate controller"
    assert info["identifiers"] == {("blebox", "abcd0123ef5678")}
    assert info["manufacturer"] == "BleBox"
    assert info["model"] == "gateController"
    assert info["sw_version"] == "1.23"


async def test_open(all_types, hass):
    """Test cover opening."""

    data = all_types
    feature_mock = data._feature_mock

    def update():
        feature_mock.state = 3  # manually stopped

    def open():
        feature_mock.state = 1  # opening

    feature_mock.async_update = CoroutineMock(side_effect=update)
    feature_mock.async_open = CoroutineMock(side_effect=open)

    entity = await data.async_updated_entity(hass, 0)

    assert_state(entity, STATE_CLOSED)
    await entity.async_open_cover()
    assert_state(entity, STATE_OPENING)


async def test_close(all_types, hass):
    """Test cover closing."""

    data = all_types
    feature_mock = data._feature_mock

    def update():
        feature_mock.state = 4  # open

    def close():
        feature_mock.state = 0  # closing

    feature_mock.async_update = CoroutineMock(side_effect=update)
    feature_mock.async_close = CoroutineMock(side_effect=close)

    entity = await data.async_updated_entity(hass, 0)

    assert_state(entity, STATE_OPEN)
    await entity.async_close_cover()
    assert_state(entity, STATE_CLOSING)


def opening_to_stop_feature_mock(data):
    """Return an mocked feature which can be updated and stopped."""
    feature_mock = data._feature_mock

    def update():
        feature_mock.state = 1  # opening

    def stop():
        feature_mock.state = 2  # manually stopped

    feature_mock.async_update = CoroutineMock(side_effect=update)
    feature_mock.async_stop = CoroutineMock(side_effect=stop)


async def test_stop(all_types, hass):
    """Test cover stopping."""

    data = all_types
    opening_to_stop_feature_mock(data)

    entity = await data.async_updated_entity(hass, 0)

    assert_state(entity, STATE_OPENING)
    await entity.async_stop_cover()
    assert_state(entity, STATE_OPEN)


async def test_update(all_types, hass):
    """Test cover updating."""

    data = all_types
    feature_mock = data._feature_mock

    def update():
        feature_mock.current = 29  # inverted
        feature_mock.state = 2  # manually stopped

    feature_mock.async_update = CoroutineMock(side_effect=update)

    entity = await data.async_updated_entity(hass, 0)

    assert entity.current_cover_position == 71  # 100 - 29
    assert_state(entity, STATE_OPEN)


def closed_to_position_almost_closed_feature_mock(data):
    """Return an mocked feature which can be updated and controlled."""
    feature_mock = data._feature_mock

    def update():
        feature_mock.state = 3  # closed

    def set_position(position):
        assert position == 99  # inverted
        feature_mock.state = 1  # opening
        # feature_mock.current = position

    feature_mock.async_update = CoroutineMock(side_effect=update)
    feature_mock.async_set_position = CoroutineMock(side_effect=set_position)


async def test_set_position(all_sliders, hass):
    """Test cover position setting."""

    data = all_sliders
    closed_to_position_almost_closed_feature_mock(data)

    entity = await data.async_updated_entity(hass, 0)

    assert_state(entity, STATE_CLOSED)
    await entity.async_set_cover_position(**{ATTR_POSITION: 1})  # almost closed
    assert_state(entity, STATE_OPENING)


async def test_fail_to_set_position(not_sliders, hass):
    """Test cover position setting."""

    data = not_sliders
    closed_to_position_almost_closed_feature_mock(data)

    entity = await data.async_updated_entity(hass, 0)

    assert_state(entity, STATE_CLOSED)
    with pytest.raises(NotImplementedError):
        await entity.async_set_cover_position(**{ATTR_POSITION: 1})  # almost closed


async def test_unknown_position(shutterbox, hass):
    """Test cover position setting."""

    data = shutterbox
    feature_mock = data._feature_mock

    def update():
        feature_mock.state = 4  # opening
        feature_mock.current = -1

    feature_mock.async_update = CoroutineMock(side_effect=update)

    with patch("homeassistant.components.blebox.cover._LOGGER.warning") as warn:
        entity = await data.async_updated_entity(hass, 0)
        assert_state(entity, STATE_OPEN)
        assert entity.current_cover_position is None
        warn.assert_has_calls(
            [
                call(
                    "Position for %s is unknown. Try calibrating the device.",
                    "shutterBox-position",
                )
            ]
        )


async def test_with_stop(gatebox, hass):
    """Test stop capability is available."""

    data = gatebox
    opening_to_stop_feature_mock(data)
    feature_mock = data._feature_mock
    feature_mock.has_stop = True

    entity = await data.async_updated_entity(hass, 0)
    assert entity.supported_features & SUPPORT_STOP


async def test_with_no_stop(gatebox, hass):
    """Test stop capability is not available."""

    data = gatebox
    opening_to_stop_feature_mock(data)
    feature_mock = data._feature_mock
    feature_mock.has_stop = False

    entity = await data.async_updated_entity(hass, 0)
    assert not entity.supported_features & SUPPORT_STOP


async def test_basic_setup(all_types, hass):
    """Run setup tests shared by all platforms."""

    data = all_types
    await DefaultBoxTest.test_update_failure(data, hass)
    await DefaultBoxTest.test_setup_failure(data, hass)
    await DefaultBoxTest.test_setup_failure_on_connection(data, hass)
