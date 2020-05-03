"""BleBox cover entities tests."""

import blebox_uniapi
import pytest

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_GATE,
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
from homeassistant.const import (
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_STOP_COVER,
    STATE_UNKNOWN,
)

from .conftest import Wrapper, mock_feature

from tests.async_mock import ANY, AsyncMock, PropertyMock, call, patch

ALL_COVER_FIXTURES = ["gatecontroller", "shutterbox", "gatebox"]


class CoverWrapper(Wrapper):
    """Wrapper for cover entities and their states."""

    @property
    def current_cover_position(self):
        """Return the attribute for the current position."""
        return self.attributes[ATTR_CURRENT_POSITION]


@pytest.fixture(name="shutterbox")
def shutterbox_fixture():
    """Return a shutterBox fixture."""
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
    return CoverWrapper(feature, "cover.shutterbox_position")


@pytest.fixture(name="gatebox")
def gatebox_fixture():
    """Return a gateBox fixture."""
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
    return CoverWrapper(feature, "cover.gatebox_position")


@pytest.fixture(name="gatecontroller")
def gate_fixture():
    """Return a gateController fixture."""
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
    return CoverWrapper(feature, "cover.gatecontroller_position")


async def test_init_gatecontroller(gatecontroller, hass, config):
    """Test gateController default state."""

    entity = gatecontroller
    await entity.setup(hass, config)

    assert entity.state.name == "gateController-position"
    assert entity.unique_id == "BleBox-gateController-2bee34e750b8-position"

    assert entity.device_class == DEVICE_CLASS_GATE

    assert entity.supported_features & SUPPORT_OPEN
    assert entity.supported_features & SUPPORT_CLOSE
    assert entity.supported_features & SUPPORT_STOP

    assert entity.supported_features & SUPPORT_SET_POSITION
    assert ATTR_CURRENT_POSITION not in entity.attributes
    assert entity.state_value == STATE_UNKNOWN

    device = await entity.device
    assert device.name == "My gate controller"
    assert device.identifiers == {("blebox", "abcd0123ef5678")}
    assert device.manufacturer == "BleBox"
    assert device.model == "gateController"
    assert device.sw_version == "1.23"


async def test_init_shutterbox(shutterbox, hass, config):
    """Test gateBox default state."""

    entity = shutterbox
    await entity.setup(hass, config)

    assert entity.state.name == "shutterBox-position"
    assert entity.unique_id == "BleBox-shutterBox-2bee34e750b8-position"

    assert entity.device_class == DEVICE_CLASS_SHUTTER

    assert entity.supported_features & SUPPORT_OPEN
    assert entity.supported_features & SUPPORT_CLOSE
    assert entity.supported_features & SUPPORT_STOP

    assert entity.supported_features & SUPPORT_SET_POSITION
    assert ATTR_CURRENT_POSITION not in entity.attributes
    assert entity.state_value == STATE_UNKNOWN

    device = await entity.device
    assert device.name == "My shutter"
    assert device.identifiers == {("blebox", "abcd0123ef5678")}
    assert device.manufacturer == "BleBox"
    assert device.model == "shutterBox"
    assert device.sw_version == "1.23"


async def test_init_gatebox(gatebox, hass, config):
    """Test cover default state."""

    entity = gatebox
    await entity.setup(hass, config)

    assert entity.state.name == "gateBox-position"
    assert entity.unique_id == "BleBox-gateBox-1afe34db9437-position"
    assert entity.device_class == DEVICE_CLASS_DOOR
    assert entity.supported_features & SUPPORT_OPEN
    assert entity.supported_features & SUPPORT_CLOSE

    # Not available during init since requires fetching state to detect
    assert not entity.supported_features & SUPPORT_STOP

    assert not entity.supported_features & SUPPORT_SET_POSITION
    assert ATTR_CURRENT_POSITION not in entity.attributes
    assert entity.state_value == STATE_UNKNOWN

    device = await entity.device
    assert device.name == "My gatebox"
    assert device.identifiers == {("blebox", "abcd0123ef5678")}
    assert device.manufacturer == "BleBox"
    assert device.model == "gateBox"
    assert device.sw_version == "1.23"


@pytest.mark.parametrize("wrapper", ALL_COVER_FIXTURES, indirect=["wrapper"])
async def test_open(wrapper, hass, config):
    """Test cover opening."""

    def initial_update():
        wrapper.feature_mock.state = 3  # manually stopped

    def open_gate():
        wrapper.feature_mock.state = 1  # opening

    wrapper.feature_mock.async_update = AsyncMock(side_effect=initial_update)
    wrapper.feature_mock.async_open = AsyncMock(side_effect=open_gate)

    await wrapper.setup(hass, config)
    assert wrapper.state_value == STATE_CLOSED
    await wrapper.service("cover", SERVICE_OPEN_COVER)
    assert wrapper.state_value == STATE_OPENING


@pytest.mark.parametrize("wrapper", ALL_COVER_FIXTURES, indirect=["wrapper"])
async def test_close(wrapper, hass, config):
    """Test cover closing."""

    def initial_update():
        wrapper.feature_mock.state = 4  # open

    def close():
        wrapper.feature_mock.state = 0  # closing

    wrapper.feature_mock.async_update = AsyncMock(side_effect=initial_update)
    wrapper.feature_mock.async_close = AsyncMock(side_effect=close)

    await wrapper.setup(hass, config)
    assert wrapper.state_value == STATE_OPEN
    await wrapper.service("cover", SERVICE_CLOSE_COVER)
    assert wrapper.state_value == STATE_CLOSING


def opening_to_stop_feature_mock(wrapper):
    """Return an mocked feature which can be updated and stopped."""

    def initial_update():
        wrapper.feature_mock.state = 1  # opening

    def stop():
        wrapper.feature_mock.state = 2  # manually stopped

    wrapper.feature_mock.async_update = AsyncMock(side_effect=initial_update)
    wrapper.feature_mock.async_stop = AsyncMock(side_effect=stop)


@pytest.mark.parametrize("wrapper", ALL_COVER_FIXTURES, indirect=["wrapper"])
async def test_stop(wrapper, hass, config):
    """Test cover stopping."""

    opening_to_stop_feature_mock(wrapper)

    await wrapper.setup(hass, config)
    assert wrapper.state_value == STATE_OPENING
    await wrapper.service("cover", SERVICE_STOP_COVER)
    assert wrapper.state_value == STATE_OPEN


@pytest.mark.parametrize("wrapper", ALL_COVER_FIXTURES, indirect=["wrapper"])
async def test_update(wrapper, hass, config):
    """Test cover updating."""

    def initial_update():
        wrapper.feature_mock.current = 29  # inverted
        wrapper.feature_mock.state = 2  # manually stopped

    wrapper.feature_mock.async_update = AsyncMock(side_effect=initial_update)

    await wrapper.setup(hass, config)
    assert wrapper.current_cover_position == 71  # 100 - 29
    assert wrapper.state_value == STATE_OPEN


def closed_to_position_almost_closed_feature_mock(wrapper):
    """Return an mocked feature which can be updated and controlled."""

    def initial_update():
        wrapper.feature_mock.state = 3  # closed

    def set_position(position):
        assert position == 99  # inverted
        wrapper.feature_mock.state = 1  # opening
        # feature_mock.current = position

    wrapper.feature_mock.async_update = AsyncMock(side_effect=initial_update)
    wrapper.feature_mock.async_set_position = AsyncMock(side_effect=set_position)


@pytest.mark.parametrize(
    "wrapper", ["gatecontroller", "shutterbox"], indirect=["wrapper"]
)
async def test_set_position(wrapper, hass, config):
    """Test cover position setting."""

    closed_to_position_almost_closed_feature_mock(wrapper)

    await wrapper.setup(hass, config)
    assert wrapper.state_value == STATE_CLOSED
    await wrapper.service(
        "cover", SERVICE_SET_COVER_POSITION, **{ATTR_POSITION: 1}
    )  # almost closed
    assert wrapper.state_value == STATE_OPENING


async def test_unknown_position(shutterbox, hass, config):
    """Test cover position setting."""

    wrapper = shutterbox

    def initial_update():
        wrapper.feature_mock.state = 4  # opening
        wrapper.feature_mock.current = -1

    wrapper.feature_mock.async_update = AsyncMock(side_effect=initial_update)

    await wrapper.setup(hass, config)
    assert wrapper.state_value == STATE_OPEN
    assert ATTR_CURRENT_POSITION not in wrapper.attributes


async def test_with_stop(gatebox, hass, config):
    """Test stop capability is available."""

    wrapper = gatebox
    opening_to_stop_feature_mock(wrapper)
    wrapper.feature_mock.has_stop = True

    await wrapper.setup(hass, config)
    assert wrapper.supported_features & SUPPORT_STOP


async def test_with_no_stop(gatebox, hass, config):
    """Test stop capability is not available."""

    wrapper = gatebox
    opening_to_stop_feature_mock(wrapper)
    wrapper.feature_mock.has_stop = False

    await wrapper.setup(hass, config)
    assert not wrapper.supported_features & SUPPORT_STOP


@pytest.mark.parametrize("wrapper", ALL_COVER_FIXTURES, indirect=["wrapper"])
async def test_update_failure(wrapper, hass, config):
    """Test that update failures are logged."""

    wrapper.feature_mock.async_update = AsyncMock(
        side_effect=blebox_uniapi.error.ClientError
    )
    name = wrapper.feature_mock.full_name

    with patch("homeassistant.components.blebox._LOGGER.error") as error:
        await wrapper.setup(hass, config)

        error.assert_has_calls([call("Updating '%s' failed: %s", name, ANY)])
        assert isinstance(error.call_args[0][2], blebox_uniapi.error.ClientError)
