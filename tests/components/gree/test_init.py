"""Tests for the Gree Integration."""
from greeclimate.exceptions import DeviceNotBoundError
import pytest

from homeassistant.components import gree
from homeassistant.components.climate.const import DOMAIN
from homeassistant.components.gree.climate import SUPPORTED_FEATURES
from homeassistant.components.gree.const import (
    CONF_DISCOVERY,
    CONF_STATIC,
    DOMAIN as GREE_DOMAIN,
)
from homeassistant.const import ATTR_SUPPORTED_FEATURES, CONF_HOST
from homeassistant.setup import async_setup_component

from tests.async_mock import AsyncMock, Mock, patch
from tests.common import MockConfigEntry, mock_coro

ENTITY_ID = f"{DOMAIN}.fake_1"
ENTITY_ID_2 = f"{DOMAIN}.fake_2"

MOCK_SIMPLE_CONFIG = {GREE_DOMAIN: {}}
MOCK_STATIC_CONFIG = {GREE_DOMAIN: {CONF_STATIC: [{CONF_HOST: "1.1.1.1"}]}}

MockDeviceInfo1 = Mock(ip="1.1.1.1", port=7000, mac="aabbcc112233")
MockDeviceInfo1.name = "fake-1"
MockDeviceInfo2 = Mock(ip="2.2.2.2", port=7000, mac="aabbcc445566")
MockDeviceInfo2.name = "fake-2"

MockDevice1 = Mock(device_info=MockDeviceInfo1, name="fake-device-1")
MockDevice1.bind = AsyncMock()

MockDevice2 = Mock(device_info=MockDeviceInfo2, name="fake-device-2")
MockDevice2.bind = AsyncMock()


@pytest.fixture(name="discovery")
def discovery_fixture():
    """Patch the discovery service."""
    with patch(
        "homeassistant.components.gree.bridge.GreeClimate.search_devices",
        new_callable=AsyncMock,
        return_value=[MockDeviceInfo1, MockDeviceInfo2],
    ) as mock:
        yield mock


@pytest.fixture(name="device")
def device_fixture():
    """Path the device search and bind."""
    with patch(
        "homeassistant.components.gree.bridge.Device",
        side_effect=[MockDevice1, MockDevice2],
    ) as mock:
        yield mock


@pytest.fixture(name="gethostname")
def hostname_fixture():
    """Patch the hostname lookup service."""
    with patch("homeassistant.components.gree.bridge.socket") as mock:
        mock.gethostbyname.side_effect = ["1.1.1.1", "2.2.2.2"]
        yield mock


async def test_setup_simple(hass, discovery, device, gethostname):
    """Test gree integration is setup."""
    await async_setup_component(hass, GREE_DOMAIN, MOCK_SIMPLE_CONFIG)
    await hass.async_block_till_done()

    # test name
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.name == "fake-1"
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == SUPPORTED_FEATURES

    state = hass.states.get(ENTITY_ID_2)
    assert state
    assert state.name == "fake-2"
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == SUPPORTED_FEATURES

    # test that we reached device bind for all devices
    assert device.call_count == 2


async def test_setup_static_discovery(hass, discovery, device, gethostname):
    """Test gree integration is setup."""
    await async_setup_component(hass, GREE_DOMAIN, MOCK_STATIC_CONFIG)
    await hass.async_block_till_done()

    # test name
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.name == "fake-1"
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == SUPPORTED_FEATURES

    state = hass.states.get(ENTITY_ID_2)
    assert state
    assert state.name == "fake-2"
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == SUPPORTED_FEATURES

    # test that we reached device bind for all devices
    assert device.call_count == 2


async def test_setup_static_only(hass, discovery, device, gethostname):
    """Test gree integration is setup."""
    conf = MOCK_STATIC_CONFIG.copy()
    conf[GREE_DOMAIN][CONF_DISCOVERY] = False

    await async_setup_component(hass, GREE_DOMAIN, MOCK_STATIC_CONFIG)
    await hass.async_block_till_done()

    # test name
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.name == "fake-1"
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == SUPPORTED_FEATURES

    state = hass.states.get(ENTITY_ID_2)
    assert state is None

    assert device.call_count == 1


async def test_setup_static_only_bad(hass, discovery, device, gethostname):
    """Test gree integration is setup."""
    gethostname.gethostbyname.side_effect = None
    gethostname.gethostbyname.return_value = "0.0.0.0"

    conf = MOCK_STATIC_CONFIG.copy()
    conf[GREE_DOMAIN][CONF_STATIC][0][CONF_HOST] = "0.0.0.0"
    conf[GREE_DOMAIN][CONF_DISCOVERY] = False

    await async_setup_component(hass, GREE_DOMAIN, MOCK_STATIC_CONFIG)
    await hass.async_block_till_done()

    # test name
    state = hass.states.get(ENTITY_ID)
    assert state is None

    state = hass.states.get(ENTITY_ID_2)
    assert state is None

    assert device.call_count == 0


async def test_setup_connection_error(hass, discovery, device, gethostname):
    """Test gree integration is setup."""
    MockDevice1 = Mock(device_info=MockDeviceInfo1, name="fake-device-1")
    MockDevice1.bind = AsyncMock(side_effect=DeviceNotBoundError)

    MockDevice2 = Mock(device_info=MockDeviceInfo2, name="fake-device-2")
    MockDevice2.bind = AsyncMock(side_effect=DeviceNotBoundError)

    device.side_effect = [MockDevice1, MockDevice2]

    await async_setup_component(hass, GREE_DOMAIN, MOCK_SIMPLE_CONFIG)
    await hass.async_block_till_done()

    # test name
    state = hass.states.get(ENTITY_ID)
    assert state is None

    state = hass.states.get(ENTITY_ID_2)
    assert state is None


async def test_setup_duplicate_config(hass, discovery, device, gethostname, caplog):
    """Test duplicate setup of platform."""
    gethostname.gethostbyname.side_effect = None
    gethostname.gethostbyname.return_value = "1.1.1.1"
    DUPLICATE = {
        GREE_DOMAIN: {CONF_STATIC: [{CONF_HOST: "1.1.1.1"}, {CONF_HOST: "1.1.1.1"}]}
    }
    await async_setup_component(hass, GREE_DOMAIN, DUPLICATE)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID) is None
    assert len(hass.states.async_all()) == 0
    assert "duplicate host entries found" in caplog.text


async def test_setup_duplicate_entries(hass, discovery, gethostname, device, caplog):
    """Test duplicate setup of platform."""
    gethostname.gethostbyname.side_effect = None
    gethostname.gethostbyname.return_value = "1.1.1.1"

    await async_setup_component(hass, GREE_DOMAIN, MOCK_SIMPLE_CONFIG)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID)
    assert hass.states.get(ENTITY_ID_2)
    assert len(hass.states.async_all()) == 2
    await async_setup_component(hass, GREE_DOMAIN, MOCK_SIMPLE_CONFIG)
    assert len(hass.states.async_all()) == 2


async def test_unload_config_entry(hass, discovery, device, gethostname):
    """Test that the async_unload_entry works."""
    # As we have currently no configuration, we just to pass the domain here.
    entry = MockConfigEntry(domain=GREE_DOMAIN)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.gree.climate.async_setup_entry",
        return_value=mock_coro(True),
    ) as light_setup:
        config = MOCK_STATIC_CONFIG.copy()
        config[GREE_DOMAIN][CONF_DISCOVERY] = False

        assert await async_setup_component(hass, GREE_DOMAIN, config)
        await hass.async_block_till_done()

        assert len(light_setup.mock_calls) == 1
        assert GREE_DOMAIN in hass.data

    assert await gree.async_unload_entry(hass, entry)
    assert hass.data[GREE_DOMAIN] == {
        "config": {"discovery": False, "hosts": [{"host": "0.0.0.0"}]}
    }
