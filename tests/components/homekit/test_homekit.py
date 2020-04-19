"""Tests for the HomeKit component."""
from unittest.mock import ANY, Mock, patch

import pytest
from zeroconf import InterfaceChoice

from homeassistant import setup
from homeassistant.components.homekit import (
    MAX_DEVICES,
    STATUS_READY,
    STATUS_RUNNING,
    STATUS_STOPPED,
    STATUS_WAIT,
    HomeKit,
)
from homeassistant.components.homekit.accessories import HomeBridge
from homeassistant.components.homekit.const import (
    AID_STORAGE,
    BRIDGE_NAME,
    CONF_AUTO_START,
    CONF_SAFE_MODE,
    DEFAULT_PORT,
    DEFAULT_SAFE_MODE,
    DOMAIN,
    HOMEKIT_FILE,
    SERVICE_HOMEKIT_RESET_ACCESSORY,
    SERVICE_HOMEKIT_START,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PORT,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import State
from homeassistant.helpers.entityfilter import generate_filter

from tests.components.homekit.common import patch_debounce

IP_ADDRESS = "127.0.0.1"
PATH_HOMEKIT = "homeassistant.components.homekit"


@pytest.fixture(scope="module")
def debounce_patcher():
    """Patch debounce method."""
    patcher = patch_debounce()
    yield patcher.start()
    patcher.stop()


async def test_setup_min(hass):
    """Test async_setup with min config options."""
    with patch(f"{PATH_HOMEKIT}.HomeKit") as mock_homekit:
        assert await setup.async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    mock_homekit.assert_any_call(
        hass, BRIDGE_NAME, DEFAULT_PORT, None, ANY, {}, DEFAULT_SAFE_MODE, None, None
    )
    assert mock_homekit().setup.called is True

    # Test auto start enabled
    mock_homekit.reset_mock()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    mock_homekit().start.assert_called_with(ANY)


async def test_setup_auto_start_disabled(hass):
    """Test async_setup with auto start disabled and test service calls."""
    config = {
        DOMAIN: {
            CONF_AUTO_START: False,
            CONF_NAME: "Test Name",
            CONF_PORT: 11111,
            CONF_IP_ADDRESS: "172.0.0.0",
            CONF_SAFE_MODE: DEFAULT_SAFE_MODE,
        }
    }

    with patch(f"{PATH_HOMEKIT}.HomeKit") as mock_homekit:
        mock_homekit.return_value = homekit = Mock()
        assert await setup.async_setup_component(hass, DOMAIN, config)

    mock_homekit.assert_any_call(
        hass, "Test Name", 11111, "172.0.0.0", ANY, {}, DEFAULT_SAFE_MODE, None, None
    )
    assert mock_homekit().setup.called is True

    # Test auto_start disabled
    homekit.reset_mock()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    assert homekit.start.called is False

    # Test start call with driver is ready
    homekit.reset_mock()
    homekit.status = STATUS_READY

    await hass.services.async_call(DOMAIN, SERVICE_HOMEKIT_START, blocking=True)
    assert homekit.start.called is True

    # Test start call with driver started
    homekit.reset_mock()
    homekit.status = STATUS_STOPPED

    await hass.services.async_call(DOMAIN, SERVICE_HOMEKIT_START, blocking=True)
    assert homekit.start.called is False


async def test_homekit_setup(hass, hk_driver):
    """Test setup of bridge and driver."""
    homekit = HomeKit(hass, BRIDGE_NAME, DEFAULT_PORT, None, {}, {}, DEFAULT_SAFE_MODE)

    with patch(
        f"{PATH_HOMEKIT}.accessories.HomeDriver", return_value=hk_driver
    ) as mock_driver, patch("homeassistant.util.get_local_ip") as mock_ip:
        mock_ip.return_value = IP_ADDRESS
        await hass.async_add_executor_job(homekit.setup)

    path = hass.config.path(HOMEKIT_FILE)
    assert isinstance(homekit.bridge, HomeBridge)
    mock_driver.assert_called_with(
        hass,
        address=IP_ADDRESS,
        port=DEFAULT_PORT,
        persist_file=path,
        advertised_address=None,
        interface_choice=None,
    )
    assert homekit.driver.safe_mode is False

    # Test if stop listener is setup
    assert hass.bus.async_listeners().get(EVENT_HOMEASSISTANT_STOP) == 1


async def test_homekit_setup_ip_address(hass, hk_driver):
    """Test setup with given IP address."""
    homekit = HomeKit(hass, BRIDGE_NAME, DEFAULT_PORT, "172.0.0.0", {}, {}, None)

    with patch(
        f"{PATH_HOMEKIT}.accessories.HomeDriver", return_value=hk_driver
    ) as mock_driver:
        await hass.async_add_executor_job(homekit.setup)
    mock_driver.assert_called_with(
        hass,
        address="172.0.0.0",
        port=DEFAULT_PORT,
        persist_file=ANY,
        advertised_address=None,
        interface_choice=None,
    )


async def test_homekit_setup_advertise_ip(hass, hk_driver):
    """Test setup with given IP address to advertise."""
    homekit = HomeKit(
        hass, BRIDGE_NAME, DEFAULT_PORT, "0.0.0.0", {}, {}, None, "192.168.1.100"
    )

    with patch(
        f"{PATH_HOMEKIT}.accessories.HomeDriver", return_value=hk_driver
    ) as mock_driver:
        await hass.async_add_executor_job(homekit.setup)
    mock_driver.assert_called_with(
        hass,
        address="0.0.0.0",
        port=DEFAULT_PORT,
        persist_file=ANY,
        advertised_address="192.168.1.100",
        interface_choice=None,
    )


async def test_homekit_setup_interface_choice(hass, hk_driver):
    """Test setup with interface choice of Default."""
    homekit = HomeKit(
        hass,
        BRIDGE_NAME,
        DEFAULT_PORT,
        "0.0.0.0",
        {},
        {},
        None,
        None,
        InterfaceChoice.Default,
    )

    with patch(
        f"{PATH_HOMEKIT}.accessories.HomeDriver", return_value=hk_driver
    ) as mock_driver:
        await hass.async_add_executor_job(homekit.setup)
    mock_driver.assert_called_with(
        hass,
        address="0.0.0.0",
        port=DEFAULT_PORT,
        persist_file=ANY,
        advertised_address=None,
        interface_choice=InterfaceChoice.Default,
    )


async def test_homekit_setup_safe_mode(hass, hk_driver):
    """Test if safe_mode flag is set."""
    homekit = HomeKit(hass, BRIDGE_NAME, DEFAULT_PORT, None, {}, {}, True, None)

    with patch(f"{PATH_HOMEKIT}.accessories.HomeDriver", return_value=hk_driver):
        await hass.async_add_executor_job(homekit.setup)
    assert homekit.driver.safe_mode is True


async def test_homekit_add_accessory(hass):
    """Add accessory if config exists and get_acc returns an accessory."""
    homekit = HomeKit(hass, None, None, None, lambda entity_id: True, {}, None, None)
    homekit.driver = "driver"
    homekit.bridge = mock_bridge = Mock()
    homekit.bridge.accessories = range(10)

    assert await setup.async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    with patch(f"{PATH_HOMEKIT}.get_accessory") as mock_get_acc:
        mock_get_acc.side_effect = [None, "acc", None]
        homekit.add_bridge_accessory(State("light.demo", "on"))
        mock_get_acc.assert_called_with(hass, "driver", ANY, 363398124, {})
        assert not mock_bridge.add_accessory.called

        homekit.add_bridge_accessory(State("demo.test", "on"))
        mock_get_acc.assert_called_with(hass, "driver", ANY, 294192020, {})
        assert mock_bridge.add_accessory.called

        homekit.add_bridge_accessory(State("demo.test_2", "on"))
        mock_get_acc.assert_called_with(hass, "driver", ANY, 429982757, {})
        mock_bridge.add_accessory.assert_called_with("acc")


async def test_homekit_remove_accessory(hass):
    """Remove accessory from bridge."""
    homekit = HomeKit("hass", None, None, None, lambda entity_id: True, {}, None, None)
    homekit.driver = "driver"
    homekit.bridge = mock_bridge = Mock()
    mock_bridge.accessories = {"light.demo": "acc"}

    acc = homekit.remove_bridge_accessory("light.demo")
    assert acc == "acc"
    assert len(mock_bridge.accessories) == 0


async def test_homekit_entity_filter(hass):
    """Test the entity filter."""
    assert await setup.async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    entity_filter = generate_filter(["cover"], ["demo.test"], [], [])
    homekit = HomeKit(hass, None, None, None, entity_filter, {}, None, None)
    homekit.bridge = Mock()
    homekit.bridge.accessories = {}

    with patch(f"{PATH_HOMEKIT}.get_accessory") as mock_get_acc:
        mock_get_acc.return_value = None

        homekit.add_bridge_accessory(State("cover.test", "open"))
        assert mock_get_acc.called is True
        mock_get_acc.reset_mock()

        homekit.add_bridge_accessory(State("demo.test", "on"))
        assert mock_get_acc.called is True
        mock_get_acc.reset_mock()

        homekit.add_bridge_accessory(State("light.demo", "light"))
        assert mock_get_acc.called is False


async def test_homekit_start(hass, hk_driver, debounce_patcher):
    """Test HomeKit start method."""
    pin = b"123-45-678"
    homekit = HomeKit(hass, None, None, None, {}, {"cover.demo": {}}, None, None)
    homekit.bridge = Mock()
    homekit.bridge.accessories = []
    homekit.driver = hk_driver

    hass.states.async_set("light.demo", "on")
    state = hass.states.async_all()[0]

    with patch(f"{PATH_HOMEKIT}.HomeKit.add_bridge_accessory") as mock_add_acc, patch(
        f"{PATH_HOMEKIT}.show_setup_message"
    ) as mock_setup_msg, patch(
        "pyhap.accessory_driver.AccessoryDriver.add_accessory"
    ) as hk_driver_add_acc, patch(
        "pyhap.accessory_driver.AccessoryDriver.start"
    ) as hk_driver_start:
        await hass.async_add_executor_job(homekit.start)

    mock_add_acc.assert_called_with(state)
    mock_setup_msg.assert_called_with(hass, pin)
    hk_driver_add_acc.assert_called_with(homekit.bridge)
    assert hk_driver_start.called
    assert homekit.status == STATUS_RUNNING

    # Test start() if already started
    hk_driver_start.reset_mock()
    await hass.async_add_executor_job(homekit.start)
    assert not hk_driver_start.called


async def test_homekit_start_with_a_broken_accessory(hass, hk_driver, debounce_patcher):
    """Test HomeKit start method."""
    pin = b"123-45-678"
    entity_filter = generate_filter(["cover", "light"], ["demo.test"], [], [])

    assert await setup.async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    homekit = HomeKit(hass, None, None, None, entity_filter, {}, None, None)
    homekit.bridge = Mock()
    homekit.bridge.accessories = []
    homekit.driver = hk_driver

    hass.states.async_set("light.demo", "on")
    hass.states.async_set("light.broken", "on")

    with patch(f"{PATH_HOMEKIT}.get_accessory", side_effect=Exception), patch(
        f"{PATH_HOMEKIT}.show_setup_message"
    ) as mock_setup_msg, patch(
        "pyhap.accessory_driver.AccessoryDriver.add_accessory",
    ) as hk_driver_add_acc, patch(
        "pyhap.accessory_driver.AccessoryDriver.start"
    ) as hk_driver_start:
        await hass.async_add_executor_job(homekit.start)

    mock_setup_msg.assert_called_with(hass, pin)
    hk_driver_add_acc.assert_called_with(homekit.bridge)
    assert hk_driver_start.called
    assert homekit.status == STATUS_RUNNING

    # Test start() if already started
    hk_driver_start.reset_mock()
    await hass.async_add_executor_job(homekit.start)
    assert not hk_driver_start.called


async def test_homekit_stop(hass):
    """Test HomeKit stop method."""
    homekit = HomeKit(hass, None, None, None, None, None, None)
    homekit.driver = Mock()

    assert homekit.status == STATUS_READY
    await hass.async_add_executor_job(homekit.stop)
    homekit.status = STATUS_WAIT
    await hass.async_add_executor_job(homekit.stop)
    homekit.status = STATUS_STOPPED
    await hass.async_add_executor_job(homekit.stop)
    assert homekit.driver.stop.called is False

    # Test if driver is started
    homekit.status = STATUS_RUNNING
    await hass.async_add_executor_job(homekit.stop)
    assert homekit.driver.stop.called is True


async def test_homekit_reset_accessories(hass):
    """Test adding too many accessories to HomeKit."""
    entity_id = "light.demo"
    homekit = HomeKit(hass, None, None, None, {}, {entity_id: {}}, None)
    homekit.bridge = Mock()
    homekit.bridge.accessories = {}

    with patch(f"{PATH_HOMEKIT}.HomeKit", return_value=homekit), patch(
        f"{PATH_HOMEKIT}.HomeKit.setup"
    ), patch("pyhap.accessory.Bridge.add_accessory") as mock_add_accessory, patch(
        "pyhap.accessory_driver.AccessoryDriver.config_changed"
    ) as hk_driver_config_changed:

        assert await setup.async_setup_component(hass, DOMAIN, {DOMAIN: {}})

        aid = hass.data[AID_STORAGE].get_or_allocate_aid_for_entity_id(entity_id)
        homekit.bridge.accessories = {aid: "acc"}
        homekit.status = STATUS_RUNNING

        await hass.services.async_call(
            DOMAIN,
            SERVICE_HOMEKIT_RESET_ACCESSORY,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert 2 == hk_driver_config_changed.call_count
        assert mock_add_accessory.called
        homekit.status = STATUS_READY


async def test_homekit_too_many_accessories(hass, hk_driver):
    """Test adding too many accessories to HomeKit."""

    entity_filter = generate_filter(["cover", "light"], ["demo.test"], [], [])

    homekit = HomeKit(hass, None, None, None, entity_filter, {}, None, None)
    homekit.bridge = Mock()
    # The bridge itself counts as an accessory
    homekit.bridge.accessories = range(MAX_DEVICES)
    homekit.driver = hk_driver

    hass.states.async_set("light.demo", "on")

    with patch("pyhap.accessory_driver.AccessoryDriver.start"), patch(
        "pyhap.accessory_driver.AccessoryDriver.add_accessory"
    ), patch("homeassistant.components.homekit._LOGGER.warning") as mock_warn:
        await hass.async_add_executor_job(homekit.start)
        assert mock_warn.called is True
