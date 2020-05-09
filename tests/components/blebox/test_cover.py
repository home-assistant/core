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
    ATTR_DEVICE_CLASS,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_STOP_COVER,
    STATE_UNKNOWN,
)

from .conftest import async_setup_entity, mock_feature

from tests.async_mock import ANY, AsyncMock, PropertyMock, call, patch

ALL_COVER_FIXTURES = ["gatecontroller", "shutterbox", "gatebox"]
FIXTURES_SUPPORTING_STOP = ["gatecontroller", "shutterbox"]


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
    return (feature, "cover.shutterbox_position")


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
    return (feature, "cover.gatebox_position")


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
    return (feature, "cover.gatecontroller_position")


async def test_init_gatecontroller(gatecontroller, hass, config):
    """Test gateController default state."""

    _, entity_id = gatecontroller
    entry = await async_setup_entity(hass, config, entity_id)
    assert entry.unique_id == "BleBox-gateController-2bee34e750b8-position"

    state = hass.states.get(entity_id)
    assert state.name == "gateController-position"
    assert state.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_GATE

    supported_features = state.attributes[ATTR_SUPPORTED_FEATURES]
    assert supported_features & SUPPORT_OPEN
    assert supported_features & SUPPORT_CLOSE
    assert supported_features & SUPPORT_STOP

    assert supported_features & SUPPORT_SET_POSITION
    assert ATTR_CURRENT_POSITION not in state.attributes
    assert state.state == STATE_UNKNOWN

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get(entry.device_id)

    assert device.name == "My gate controller"
    assert device.identifiers == {("blebox", "abcd0123ef5678")}
    assert device.manufacturer == "BleBox"
    assert device.model == "gateController"
    assert device.sw_version == "1.23"


async def test_init_shutterbox(shutterbox, hass, config):
    """Test gateBox default state."""

    _, entity_id = shutterbox
    entry = await async_setup_entity(hass, config, entity_id)
    assert entry.unique_id == "BleBox-shutterBox-2bee34e750b8-position"

    state = hass.states.get(entity_id)
    assert state.name == "shutterBox-position"
    assert entry.device_class == DEVICE_CLASS_SHUTTER

    supported_features = state.attributes[ATTR_SUPPORTED_FEATURES]
    assert supported_features & SUPPORT_OPEN
    assert supported_features & SUPPORT_CLOSE
    assert supported_features & SUPPORT_STOP

    assert supported_features & SUPPORT_SET_POSITION
    assert ATTR_CURRENT_POSITION not in state.attributes
    assert state.state == STATE_UNKNOWN

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get(entry.device_id)

    assert device.name == "My shutter"
    assert device.identifiers == {("blebox", "abcd0123ef5678")}
    assert device.manufacturer == "BleBox"
    assert device.model == "shutterBox"
    assert device.sw_version == "1.23"


async def test_init_gatebox(gatebox, hass, config):
    """Test cover default state."""

    _, entity_id = gatebox
    entry = await async_setup_entity(hass, config, entity_id)
    assert entry.unique_id == "BleBox-gateBox-1afe34db9437-position"

    state = hass.states.get(entity_id)
    assert state.name == "gateBox-position"
    assert state.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_DOOR

    supported_features = state.attributes[ATTR_SUPPORTED_FEATURES]
    assert supported_features & SUPPORT_OPEN
    assert supported_features & SUPPORT_CLOSE

    # Not available during init since requires fetching state to detect
    assert not supported_features & SUPPORT_STOP

    assert not supported_features & SUPPORT_SET_POSITION
    assert ATTR_CURRENT_POSITION not in state.attributes
    assert state.state == STATE_UNKNOWN

    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get(entry.device_id)

    assert device.name == "My gatebox"
    assert device.identifiers == {("blebox", "abcd0123ef5678")}
    assert device.manufacturer == "BleBox"
    assert device.model == "gateBox"
    assert device.sw_version == "1.23"


@pytest.mark.parametrize("wrapper", ALL_COVER_FIXTURES, indirect=["wrapper"])
async def test_open(wrapper, hass, config):
    """Test cover opening."""

    feature_mock, entity_id = wrapper

    def initial_update():
        feature_mock.state = 3  # manually stopped

    def open_gate():
        feature_mock.state = 1  # opening

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    feature_mock.async_open = AsyncMock(side_effect=open_gate)

    await async_setup_entity(hass, config, entity_id)
    assert hass.states.get(entity_id).state == STATE_CLOSED

    feature_mock.async_update = AsyncMock()
    await hass.services.async_call(
        "cover", SERVICE_OPEN_COVER, {"entity_id": entity_id}, blocking=True,
    )
    assert hass.states.get(entity_id).state == STATE_OPENING


@pytest.mark.parametrize("wrapper", ALL_COVER_FIXTURES, indirect=["wrapper"])
async def test_close(wrapper, hass, config):
    """Test cover closing."""

    feature_mock, entity_id = wrapper

    def initial_update():
        feature_mock.state = 4  # open

    def close():
        feature_mock.state = 0  # closing

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    feature_mock.async_close = AsyncMock(side_effect=close)

    await async_setup_entity(hass, config, entity_id)
    assert hass.states.get(entity_id).state == STATE_OPEN

    feature_mock.async_update = AsyncMock()
    await hass.services.async_call(
        "cover", SERVICE_CLOSE_COVER, {"entity_id": entity_id}, blocking=True
    )
    assert hass.states.get(entity_id).state == STATE_CLOSING


def opening_to_stop_feature_mock(feature_mock):
    """Return an mocked feature which can be updated and stopped."""

    def initial_update():
        feature_mock.state = 1  # opening

    def stop():
        feature_mock.state = 2  # manually stopped

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    feature_mock.async_stop = AsyncMock(side_effect=stop)


@pytest.mark.parametrize("wrapper", FIXTURES_SUPPORTING_STOP, indirect=["wrapper"])
async def test_stop(wrapper, hass, config):
    """Test cover stopping."""

    feature_mock, entity_id = wrapper
    opening_to_stop_feature_mock(feature_mock)

    await async_setup_entity(hass, config, entity_id)
    assert hass.states.get(entity_id).state == STATE_OPENING

    feature_mock.async_update = AsyncMock()
    await hass.services.async_call(
        "cover", SERVICE_STOP_COVER, {"entity_id": entity_id}, blocking=True
    )
    assert hass.states.get(entity_id).state == STATE_OPEN


@pytest.mark.parametrize("wrapper", ALL_COVER_FIXTURES, indirect=["wrapper"])
async def test_update(wrapper, hass, config):
    """Test cover updating."""

    feature_mock, entity_id = wrapper

    def initial_update():
        feature_mock.current = 29  # inverted
        feature_mock.state = 2  # manually stopped

    feature_mock.async_update = AsyncMock(side_effect=initial_update)

    await async_setup_entity(hass, config, entity_id)

    state = hass.states.get(entity_id)
    assert state.attributes[ATTR_CURRENT_POSITION] == 71  # 100 - 29
    assert state.state == STATE_OPEN


@pytest.mark.parametrize(
    "wrapper", ["gatecontroller", "shutterbox"], indirect=["wrapper"]
)
async def test_set_position(wrapper, hass, config):
    """Test cover position setting."""

    feature_mock, entity_id = wrapper

    def initial_update():
        feature_mock.state = 3  # closed

    def set_position(position):
        assert position == 99  # inverted
        feature_mock.state = 1  # opening
        # feature_mock.current = position

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    feature_mock.async_set_position = AsyncMock(side_effect=set_position)

    await async_setup_entity(hass, config, entity_id)
    assert hass.states.get(entity_id).state == STATE_CLOSED

    feature_mock.async_update = AsyncMock()
    await hass.services.async_call(
        "cover",
        SERVICE_SET_COVER_POSITION,
        {"entity_id": entity_id, ATTR_POSITION: 1},
        blocking=True,
    )  # almost closed
    assert hass.states.get(entity_id).state == STATE_OPENING


async def test_unknown_position(shutterbox, hass, config):
    """Test cover position setting."""

    feature_mock, entity_id = shutterbox

    def initial_update():
        feature_mock.state = 4  # opening
        feature_mock.current = -1

    feature_mock.async_update = AsyncMock(side_effect=initial_update)

    await async_setup_entity(hass, config, entity_id)

    state = hass.states.get(entity_id)
    assert state.state == STATE_OPEN
    assert ATTR_CURRENT_POSITION not in state.attributes


async def test_with_stop(gatebox, hass, config):
    """Test stop capability is available."""

    feature_mock, entity_id = gatebox
    opening_to_stop_feature_mock(feature_mock)
    feature_mock.has_stop = True

    await async_setup_entity(hass, config, entity_id)

    state = hass.states.get(entity_id)
    supported_features = state.attributes[ATTR_SUPPORTED_FEATURES]
    assert supported_features & SUPPORT_STOP


async def test_with_no_stop(gatebox, hass, config):
    """Test stop capability is not available."""

    feature_mock, entity_id = gatebox
    opening_to_stop_feature_mock(feature_mock)
    feature_mock.has_stop = False

    await async_setup_entity(hass, config, entity_id)

    state = hass.states.get(entity_id)
    supported_features = state.attributes[ATTR_SUPPORTED_FEATURES]
    assert not supported_features & SUPPORT_STOP


@pytest.mark.parametrize("wrapper", ALL_COVER_FIXTURES, indirect=["wrapper"])
async def test_update_failure(wrapper, hass, config):
    """Test that update failures are logged."""

    feature_mock, entity_id = wrapper

    feature_mock.async_update = AsyncMock(side_effect=blebox_uniapi.error.ClientError)
    name = feature_mock.full_name

    with patch("homeassistant.components.blebox._LOGGER.error") as error:
        await async_setup_entity(hass, config, entity_id)

        error.assert_has_calls([call("Updating '%s' failed: %s", name, ANY)])
        assert isinstance(error.call_args[0][2], blebox_uniapi.error.ClientError)
