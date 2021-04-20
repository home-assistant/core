"""Blebox switch tests."""
import logging
from unittest.mock import AsyncMock, PropertyMock

import blebox_uniapi
import pytest

from homeassistant.components.switch import DEVICE_CLASS_SWITCH
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.helpers import device_registry as dr

from .conftest import (
    async_setup_entities,
    async_setup_entity,
    mock_feature,
    mock_only_feature,
    setup_product_mock,
)


@pytest.fixture(name="switchbox")
def switchbox_fixture():
    """Return a default switchBox switch entity mock."""
    feature = mock_feature(
        "switches",
        blebox_uniapi.switch.Switch,
        unique_id="BleBox-switchBox-1afe34e750b8-0.relay",
        full_name="switchBox-0.relay",
        device_class="relay",
        is_on=False,
    )
    feature.async_update = AsyncMock()
    product = feature.product
    type(product).name = PropertyMock(return_value="My switch box")
    type(product).model = PropertyMock(return_value="switchBox")
    return (feature, "switch.switchbox_0_relay")


async def test_switchbox_init(switchbox, hass, config):
    """Test switch default state."""

    feature_mock, entity_id = switchbox

    feature_mock.async_update = AsyncMock()
    entry = await async_setup_entity(hass, config, entity_id)
    assert entry.unique_id == "BleBox-switchBox-1afe34e750b8-0.relay"

    state = hass.states.get(entity_id)
    assert state.name == "switchBox-0.relay"

    assert state.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_SWITCH

    assert state.state == STATE_OFF

    device_registry = dr.async_get(hass)
    device = device_registry.async_get(entry.device_id)

    assert device.name == "My switch box"
    assert device.identifiers == {("blebox", "abcd0123ef5678")}
    assert device.manufacturer == "BleBox"
    assert device.model == "switchBox"
    assert device.sw_version == "1.23"


async def test_switchbox_update_when_off(switchbox, hass, config):
    """Test switch updating when off."""

    feature_mock, entity_id = switchbox

    def initial_update():
        feature_mock.is_on = False

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, config, entity_id)

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF


async def test_switchbox_update_when_on(switchbox, hass, config):
    """Test switch updating when on."""

    feature_mock, entity_id = switchbox

    def initial_update():
        feature_mock.is_on = True

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, config, entity_id)

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON


async def test_switchbox_on(switchbox, hass, config):
    """Test turning switch on."""

    feature_mock, entity_id = switchbox

    def initial_update():
        feature_mock.is_on = False

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, config, entity_id)
    feature_mock.async_update = AsyncMock()

    def turn_on():
        feature_mock.is_on = True

    feature_mock.async_turn_on = AsyncMock(side_effect=turn_on)

    await hass.services.async_call(
        "switch",
        SERVICE_TURN_ON,
        {"entity_id": entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON


async def test_switchbox_off(switchbox, hass, config):
    """Test turning switch off."""

    feature_mock, entity_id = switchbox

    def initial_update():
        feature_mock.is_on = True

    feature_mock.async_update = AsyncMock(side_effect=initial_update)
    await async_setup_entity(hass, config, entity_id)
    feature_mock.async_update = AsyncMock()

    def turn_off():
        feature_mock.is_on = False

    feature_mock.async_turn_off = AsyncMock(side_effect=turn_off)

    await hass.services.async_call(
        "switch",
        SERVICE_TURN_OFF,
        {"entity_id": entity_id},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF


def relay_mock(relay_id=0):
    """Return a default switchBoxD switch entity mock."""

    return mock_only_feature(
        blebox_uniapi.switch.Switch,
        unique_id=f"BleBox-switchBoxD-1afe34e750b8-{relay_id}.relay",
        full_name=f"switchBoxD-{relay_id}.relay",
        device_class="relay",
        is_on=None,
    )


@pytest.fixture(name="switchbox_d")
def switchbox_d_fixture():
    """Set up two mocked Switch features representing a switchBoxD."""

    relay1 = relay_mock(0)
    relay2 = relay_mock(1)
    features = [relay1, relay2]

    product = setup_product_mock("switches", features)

    type(product).name = PropertyMock(return_value="My relays")
    type(product).model = PropertyMock(return_value="switchBoxD")
    type(product).brand = PropertyMock(return_value="BleBox")
    type(product).firmware_version = PropertyMock(return_value="1.23")
    type(product).unique_id = PropertyMock(return_value="abcd0123ef5678")

    type(relay1).product = product
    type(relay2).product = product

    return (features, ["switch.switchboxd_0_relay", "switch.switchboxd_1_relay"])


async def test_switchbox_d_init(switchbox_d, hass, config):
    """Test switch default state."""

    feature_mocks, entity_ids = switchbox_d

    feature_mocks[0].async_update = AsyncMock()
    feature_mocks[1].async_update = AsyncMock()
    entries = await async_setup_entities(hass, config, entity_ids)

    entry = entries[0]
    assert entry.unique_id == "BleBox-switchBoxD-1afe34e750b8-0.relay"

    state = hass.states.get(entity_ids[0])
    assert state.name == "switchBoxD-0.relay"
    assert state.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_SWITCH
    assert state.state == STATE_OFF  # NOTE: should instead be STATE_UNKNOWN?

    device_registry = dr.async_get(hass)
    device = device_registry.async_get(entry.device_id)

    assert device.name == "My relays"
    assert device.identifiers == {("blebox", "abcd0123ef5678")}
    assert device.manufacturer == "BleBox"
    assert device.model == "switchBoxD"
    assert device.sw_version == "1.23"

    entry = entries[1]
    assert entry.unique_id == "BleBox-switchBoxD-1afe34e750b8-1.relay"

    state = hass.states.get(entity_ids[1])
    assert state.name == "switchBoxD-1.relay"
    assert state.attributes[ATTR_DEVICE_CLASS] == DEVICE_CLASS_SWITCH
    assert state.state == STATE_OFF  # NOTE: should instead be STATE_UNKNOWN?

    device_registry = dr.async_get(hass)
    device = device_registry.async_get(entry.device_id)

    assert device.name == "My relays"
    assert device.identifiers == {("blebox", "abcd0123ef5678")}
    assert device.manufacturer == "BleBox"
    assert device.model == "switchBoxD"
    assert device.sw_version == "1.23"


async def test_switchbox_d_update_when_off(switchbox_d, hass, config):
    """Test switch updating when off."""

    feature_mocks, entity_ids = switchbox_d

    def initial_update0():
        feature_mocks[0].is_on = False
        feature_mocks[1].is_on = False

    feature_mocks[0].async_update = AsyncMock(side_effect=initial_update0)
    feature_mocks[1].async_update = AsyncMock()
    await async_setup_entities(hass, config, entity_ids)

    assert hass.states.get(entity_ids[0]).state == STATE_OFF
    assert hass.states.get(entity_ids[1]).state == STATE_OFF


async def test_switchbox_d_update_when_second_off(switchbox_d, hass, config):
    """Test switch updating when off."""

    feature_mocks, entity_ids = switchbox_d

    def initial_update0():
        feature_mocks[0].is_on = True
        feature_mocks[1].is_on = False

    feature_mocks[0].async_update = AsyncMock(side_effect=initial_update0)
    feature_mocks[1].async_update = AsyncMock()
    await async_setup_entities(hass, config, entity_ids)

    assert hass.states.get(entity_ids[0]).state == STATE_ON
    assert hass.states.get(entity_ids[1]).state == STATE_OFF


async def test_switchbox_d_turn_first_on(switchbox_d, hass, config):
    """Test turning switch on."""

    feature_mocks, entity_ids = switchbox_d

    def initial_update0():
        feature_mocks[0].is_on = False
        feature_mocks[1].is_on = False

    feature_mocks[0].async_update = AsyncMock(side_effect=initial_update0)
    feature_mocks[1].async_update = AsyncMock()
    await async_setup_entities(hass, config, entity_ids)
    feature_mocks[0].async_update = AsyncMock()

    def turn_on0():
        feature_mocks[0].is_on = True

    feature_mocks[0].async_turn_on = AsyncMock(side_effect=turn_on0)
    await hass.services.async_call(
        "switch",
        SERVICE_TURN_ON,
        {"entity_id": entity_ids[0]},
        blocking=True,
    )

    assert hass.states.get(entity_ids[0]).state == STATE_ON
    assert hass.states.get(entity_ids[1]).state == STATE_OFF


async def test_switchbox_d_second_on(switchbox_d, hass, config):
    """Test turning switch on."""

    feature_mocks, entity_ids = switchbox_d

    def initial_update0():
        feature_mocks[0].is_on = False
        feature_mocks[1].is_on = False

    feature_mocks[0].async_update = AsyncMock(side_effect=initial_update0)
    feature_mocks[1].async_update = AsyncMock()
    await async_setup_entities(hass, config, entity_ids)
    feature_mocks[0].async_update = AsyncMock()

    def turn_on1():
        feature_mocks[1].is_on = True

    feature_mocks[1].async_turn_on = AsyncMock(side_effect=turn_on1)
    await hass.services.async_call(
        "switch",
        SERVICE_TURN_ON,
        {"entity_id": entity_ids[1]},
        blocking=True,
    )

    assert hass.states.get(entity_ids[0]).state == STATE_OFF
    assert hass.states.get(entity_ids[1]).state == STATE_ON


async def test_switchbox_d_first_off(switchbox_d, hass, config):
    """Test turning switch on."""

    feature_mocks, entity_ids = switchbox_d

    def initial_update_any():
        feature_mocks[0].is_on = True
        feature_mocks[1].is_on = True

    feature_mocks[0].async_update = AsyncMock(side_effect=initial_update_any)
    feature_mocks[1].async_update = AsyncMock()
    await async_setup_entities(hass, config, entity_ids)
    feature_mocks[0].async_update = AsyncMock()

    def turn_off0():
        feature_mocks[0].is_on = False

    feature_mocks[0].async_turn_off = AsyncMock(side_effect=turn_off0)
    await hass.services.async_call(
        "switch",
        SERVICE_TURN_OFF,
        {"entity_id": entity_ids[0]},
        blocking=True,
    )

    assert hass.states.get(entity_ids[0]).state == STATE_OFF
    assert hass.states.get(entity_ids[1]).state == STATE_ON


async def test_switchbox_d_second_off(switchbox_d, hass, config):
    """Test turning switch on."""

    feature_mocks, entity_ids = switchbox_d

    def initial_update_any():
        feature_mocks[0].is_on = True
        feature_mocks[1].is_on = True

    feature_mocks[0].async_update = AsyncMock(side_effect=initial_update_any)
    feature_mocks[1].async_update = AsyncMock()
    await async_setup_entities(hass, config, entity_ids)
    feature_mocks[0].async_update = AsyncMock()

    def turn_off1():
        feature_mocks[1].is_on = False

    feature_mocks[1].async_turn_off = AsyncMock(side_effect=turn_off1)
    await hass.services.async_call(
        "switch",
        SERVICE_TURN_OFF,
        {"entity_id": entity_ids[1]},
        blocking=True,
    )
    assert hass.states.get(entity_ids[0]).state == STATE_ON
    assert hass.states.get(entity_ids[1]).state == STATE_OFF


ALL_SWITCH_FIXTURES = ["switchbox", "switchbox_d"]


@pytest.mark.parametrize("feature", ALL_SWITCH_FIXTURES, indirect=["feature"])
async def test_update_failure(feature, hass, config, caplog):
    """Test that update failures are logged."""

    caplog.set_level(logging.ERROR)

    feature_mock, entity_id = feature

    if isinstance(feature_mock, list):
        feature_mock[0].async_update = AsyncMock()
        feature_mock[1].async_update = AsyncMock()
        feature_mock = feature_mock[0]
        entity_id = entity_id[0]

    feature_mock.async_update = AsyncMock(side_effect=blebox_uniapi.error.ClientError)
    await async_setup_entity(hass, config, entity_id)

    assert f"Updating '{feature_mock.full_name}' failed: " in caplog.text
