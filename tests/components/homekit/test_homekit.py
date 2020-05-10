"""Tests for the HomeKit component."""
import os
from typing import Dict

import pytest
from zeroconf import InterfaceChoice

from homeassistant.components.binary_sensor import DEVICE_CLASS_BATTERY_CHARGING
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
    CONF_ENTRY_INDEX,
    CONF_SAFE_MODE,
    CONF_ZEROCONF_DEFAULT_INTERFACE,
    DEFAULT_PORT,
    DEFAULT_SAFE_MODE,
    DOMAIN,
    HOMEKIT_FILE,
    SERVICE_HOMEKIT_RESET_ACCESSORY,
    SERVICE_HOMEKIT_START,
)
from homeassistant.components.homekit.util import (
    get_aid_storage_fullpath_for_entry_id,
    get_persist_fullpath_for_entry_id,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_PORT,
    DEVICE_CLASS_BATTERY,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    STATE_ON,
)
from homeassistant.core import State
from homeassistant.helpers import device_registry
from homeassistant.helpers.entityfilter import generate_filter
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.setup import async_setup_component
from homeassistant.util import json as json_util

from .util import PATH_HOMEKIT, async_init_entry, async_init_integration

from tests.async_mock import ANY, AsyncMock, Mock, patch
from tests.common import MockConfigEntry, mock_device_registry, mock_registry
from tests.components.homekit.common import patch_debounce

IP_ADDRESS = "127.0.0.1"


@pytest.fixture
def device_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture
def entity_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


@pytest.fixture(scope="module")
def debounce_patcher():
    """Patch debounce method."""
    patcher = patch_debounce()
    yield patcher.start()
    patcher.stop()


async def test_setup_min(hass):
    """Test async_setup with min config options."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: BRIDGE_NAME, CONF_PORT: DEFAULT_PORT},
        options={},
    )
    entry.add_to_hass(hass)

    with patch(f"{PATH_HOMEKIT}.HomeKit") as mock_homekit:
        mock_homekit.return_value = homekit = Mock()
        type(homekit).async_start = AsyncMock()
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    mock_homekit.assert_any_call(
        hass,
        BRIDGE_NAME,
        DEFAULT_PORT,
        None,
        ANY,
        {},
        DEFAULT_SAFE_MODE,
        None,
        None,
        entry.entry_id,
    )
    assert mock_homekit().setup.called is True

    # Test auto start enabled
    mock_homekit.reset_mock()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    mock_homekit().async_start.assert_called()


async def test_setup_auto_start_disabled(hass):
    """Test async_setup with auto start disabled and test service calls."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: "Test Name", CONF_PORT: 11111, CONF_IP_ADDRESS: "172.0.0.0"},
        options={
            CONF_AUTO_START: False,
            CONF_SAFE_MODE: DEFAULT_SAFE_MODE,
            CONF_ZEROCONF_DEFAULT_INTERFACE: True,
        },
    )
    entry.add_to_hass(hass)

    with patch(f"{PATH_HOMEKIT}.HomeKit") as mock_homekit:
        mock_homekit.return_value = homekit = Mock()
        type(homekit).async_start = AsyncMock()
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    mock_homekit.assert_any_call(
        hass,
        "Test Name",
        11111,
        "172.0.0.0",
        ANY,
        {},
        DEFAULT_SAFE_MODE,
        None,
        InterfaceChoice.Default,
        entry.entry_id,
    )
    assert mock_homekit().setup.called is True

    # Test auto_start disabled
    homekit.reset_mock()
    homekit.async_start.reset_mock()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    assert homekit.async_start.called is False

    # Test start call with driver is ready
    homekit.reset_mock()
    homekit.async_start.reset_mock()
    homekit.status = STATUS_READY

    await hass.services.async_call(DOMAIN, SERVICE_HOMEKIT_START, blocking=True)
    await hass.async_block_till_done()
    assert homekit.async_start.called is True

    # Test start call with driver started
    homekit.reset_mock()
    homekit.async_start.reset_mock()
    homekit.status = STATUS_STOPPED

    await hass.services.async_call(DOMAIN, SERVICE_HOMEKIT_START, blocking=True)
    await hass.async_block_till_done()
    assert homekit.async_start.called is False


async def test_homekit_setup(hass, hk_driver):
    """Test setup of bridge and driver."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: "mock_name", CONF_PORT: 12345},
        source=SOURCE_IMPORT,
    )
    homekit = HomeKit(
        hass,
        BRIDGE_NAME,
        DEFAULT_PORT,
        None,
        {},
        {},
        DEFAULT_SAFE_MODE,
        advertise_ip=None,
        interface_choice=None,
        entry_id=entry.entry_id,
    )

    with patch(
        f"{PATH_HOMEKIT}.accessories.HomeDriver", return_value=hk_driver
    ) as mock_driver, patch("homeassistant.util.get_local_ip") as mock_ip:
        mock_ip.return_value = IP_ADDRESS
        await hass.async_add_executor_job(homekit.setup)

    path = get_persist_fullpath_for_entry_id(hass, entry.entry_id)
    assert isinstance(homekit.bridge, HomeBridge)
    mock_driver.assert_called_with(
        hass,
        entry.entry_id,
        BRIDGE_NAME,
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
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: "mock_name", CONF_PORT: 12345},
        source=SOURCE_IMPORT,
    )
    homekit = HomeKit(
        hass,
        BRIDGE_NAME,
        DEFAULT_PORT,
        "172.0.0.0",
        {},
        {},
        None,
        None,
        interface_choice=None,
        entry_id=entry.entry_id,
    )

    path = get_persist_fullpath_for_entry_id(hass, entry.entry_id)
    with patch(
        f"{PATH_HOMEKIT}.accessories.HomeDriver", return_value=hk_driver
    ) as mock_driver:
        await hass.async_add_executor_job(homekit.setup)
    mock_driver.assert_called_with(
        hass,
        entry.entry_id,
        BRIDGE_NAME,
        address="172.0.0.0",
        port=DEFAULT_PORT,
        persist_file=path,
        advertised_address=None,
        interface_choice=None,
    )


async def test_homekit_setup_advertise_ip(hass, hk_driver):
    """Test setup with given IP address to advertise."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: "mock_name", CONF_PORT: 12345},
        source=SOURCE_IMPORT,
    )
    homekit = HomeKit(
        hass,
        BRIDGE_NAME,
        DEFAULT_PORT,
        "0.0.0.0",
        {},
        {},
        None,
        "192.168.1.100",
        interface_choice=None,
        entry_id=entry.entry_id,
    )

    path = get_persist_fullpath_for_entry_id(hass, entry.entry_id)
    with patch(
        f"{PATH_HOMEKIT}.accessories.HomeDriver", return_value=hk_driver
    ) as mock_driver:
        await hass.async_add_executor_job(homekit.setup)
    mock_driver.assert_called_with(
        hass,
        entry.entry_id,
        BRIDGE_NAME,
        address="0.0.0.0",
        port=DEFAULT_PORT,
        persist_file=path,
        advertised_address="192.168.1.100",
        interface_choice=None,
    )


async def test_homekit_setup_interface_choice(hass, hk_driver):
    """Test setup with interface choice of Default."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: "mock_name", CONF_PORT: 12345},
        source=SOURCE_IMPORT,
    )
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
        entry_id=entry.entry_id,
    )

    path = get_persist_fullpath_for_entry_id(hass, entry.entry_id)
    with patch(
        f"{PATH_HOMEKIT}.accessories.HomeDriver", return_value=hk_driver
    ) as mock_driver:
        await hass.async_add_executor_job(homekit.setup)
    mock_driver.assert_called_with(
        hass,
        entry.entry_id,
        BRIDGE_NAME,
        address="0.0.0.0",
        port=DEFAULT_PORT,
        persist_file=path,
        advertised_address=None,
        interface_choice=InterfaceChoice.Default,
    )


async def test_homekit_setup_safe_mode(hass, hk_driver):
    """Test if safe_mode flag is set."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: "mock_name", CONF_PORT: 12345},
        source=SOURCE_IMPORT,
    )
    homekit = HomeKit(
        hass,
        BRIDGE_NAME,
        DEFAULT_PORT,
        None,
        {},
        {},
        True,
        advertise_ip=None,
        interface_choice=None,
        entry_id=entry.entry_id,
    )

    with patch(f"{PATH_HOMEKIT}.accessories.HomeDriver", return_value=hk_driver):
        await hass.async_add_executor_job(homekit.setup)
    assert homekit.driver.safe_mode is True


async def test_homekit_add_accessory(hass):
    """Add accessory if config exists and get_acc returns an accessory."""
    entry = await async_init_integration(hass)

    homekit = HomeKit(
        hass,
        None,
        None,
        None,
        lambda entity_id: True,
        {},
        DEFAULT_SAFE_MODE,
        advertise_ip=None,
        interface_choice=None,
        entry_id=entry.entry_id,
    )
    homekit.driver = "driver"
    homekit.bridge = mock_bridge = Mock()
    homekit.bridge.accessories = range(10)

    await async_init_integration(hass)

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
    entry = await async_init_integration(hass)

    homekit = HomeKit(
        hass,
        None,
        None,
        None,
        lambda entity_id: True,
        {},
        DEFAULT_SAFE_MODE,
        advertise_ip=None,
        interface_choice=None,
        entry_id=entry.entry_id,
    )
    homekit.driver = "driver"
    homekit.bridge = mock_bridge = Mock()
    mock_bridge.accessories = {"light.demo": "acc"}

    acc = homekit.remove_bridge_accessory("light.demo")
    assert acc == "acc"
    assert len(mock_bridge.accessories) == 0


async def test_homekit_entity_filter(hass):
    """Test the entity filter."""
    entry = await async_init_integration(hass)

    entity_filter = generate_filter(["cover"], ["demo.test"], [], [])
    homekit = HomeKit(
        hass,
        None,
        None,
        None,
        entity_filter,
        {},
        DEFAULT_SAFE_MODE,
        advertise_ip=None,
        interface_choice=None,
        entry_id=entry.entry_id,
    )
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
    entry = await async_init_integration(hass)

    pin = b"123-45-678"
    homekit = HomeKit(
        hass,
        None,
        None,
        None,
        {},
        {},
        DEFAULT_SAFE_MODE,
        advertise_ip=None,
        interface_choice=None,
        entry_id=entry.entry_id,
    )
    homekit.bridge = Mock()
    homekit.bridge.accessories = []
    homekit.driver = hk_driver
    homekit._filter = Mock(return_value=True)

    hass.states.async_set("light.demo", "on")
    state = hass.states.async_all()[0]

    with patch(f"{PATH_HOMEKIT}.HomeKit.add_bridge_accessory") as mock_add_acc, patch(
        f"{PATH_HOMEKIT}.show_setup_message"
    ) as mock_setup_msg, patch(
        "pyhap.accessory_driver.AccessoryDriver.add_accessory"
    ) as hk_driver_add_acc, patch(
        "pyhap.accessory_driver.AccessoryDriver.start"
    ) as hk_driver_start:
        await homekit.async_start()

    await hass.async_block_till_done()
    mock_add_acc.assert_called_with(state)
    mock_setup_msg.assert_called_with(hass, entry.entry_id, None, pin, ANY)
    hk_driver_add_acc.assert_called_with(homekit.bridge)
    assert hk_driver_start.called
    assert homekit.status == STATUS_RUNNING

    # Test start() if already started
    hk_driver_start.reset_mock()
    await homekit.async_start()
    await hass.async_block_till_done()
    assert not hk_driver_start.called


async def test_homekit_start_with_a_broken_accessory(hass, hk_driver, debounce_patcher):
    """Test HomeKit start method."""
    pin = b"123-45-678"
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entity_filter = generate_filter(["cover", "light"], ["demo.test"], [], [])

    await async_init_entry(hass, entry)
    homekit = HomeKit(
        hass,
        None,
        None,
        None,
        entity_filter,
        {},
        DEFAULT_SAFE_MODE,
        advertise_ip=None,
        interface_choice=None,
        entry_id=entry.entry_id,
    )

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
        await homekit.async_start()

    await hass.async_block_till_done()
    mock_setup_msg.assert_called_with(hass, entry.entry_id, None, pin, ANY)
    hk_driver_add_acc.assert_called_with(homekit.bridge)
    assert hk_driver_start.called
    assert homekit.status == STATUS_RUNNING

    # Test start() if already started
    hk_driver_start.reset_mock()
    await homekit.async_start()
    await hass.async_block_till_done()
    assert not hk_driver_start.called


async def test_homekit_stop(hass):
    """Test HomeKit stop method."""
    entry = await async_init_integration(hass)

    homekit = HomeKit(
        hass,
        None,
        None,
        None,
        {},
        {},
        DEFAULT_SAFE_MODE,
        advertise_ip=None,
        interface_choice=None,
        entry_id=entry.entry_id,
    )
    homekit.driver = Mock()

    await async_init_integration(hass)

    assert homekit.status == STATUS_READY
    await homekit.async_stop()
    await hass.async_block_till_done()
    homekit.status = STATUS_WAIT
    await homekit.async_stop()
    await hass.async_block_till_done()
    homekit.status = STATUS_STOPPED
    await homekit.async_stop()
    await hass.async_block_till_done()
    assert homekit.driver.stop.called is False

    # Test if driver is started
    homekit.status = STATUS_RUNNING
    await homekit.async_stop()
    await hass.async_block_till_done()
    assert homekit.driver.stop.called is True


async def test_homekit_reset_accessories(hass):
    """Test adding too many accessories to HomeKit."""

    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entity_id = "light.demo"
    homekit = HomeKit(
        hass,
        None,
        None,
        None,
        {},
        {entity_id: {}},
        DEFAULT_SAFE_MODE,
        advertise_ip=None,
        interface_choice=None,
        entry_id=entry.entry_id,
    )
    homekit.bridge = Mock()
    homekit.bridge.accessories = {}

    with patch(f"{PATH_HOMEKIT}.HomeKit", return_value=homekit), patch(
        f"{PATH_HOMEKIT}.HomeKit.setup"
    ), patch("pyhap.accessory.Bridge.add_accessory") as mock_add_accessory, patch(
        "pyhap.accessory_driver.AccessoryDriver.config_changed"
    ) as hk_driver_config_changed, patch(
        "pyhap.accessory_driver.AccessoryDriver.start"
    ):
        await async_init_entry(hass, entry)

        aid = hass.data[DOMAIN][entry.entry_id][
            AID_STORAGE
        ].get_or_allocate_aid_for_entity_id(entity_id)
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
    entry = await async_init_integration(hass)

    entity_filter = generate_filter(["cover", "light"], ["demo.test"], [], [])

    homekit = HomeKit(
        hass,
        None,
        None,
        None,
        entity_filter,
        {},
        DEFAULT_SAFE_MODE,
        advertise_ip=None,
        interface_choice=None,
        entry_id=entry.entry_id,
    )
    homekit.bridge = Mock()
    # The bridge itself counts as an accessory
    homekit.bridge.accessories = range(MAX_DEVICES)
    homekit.driver = hk_driver

    hass.states.async_set("light.demo", "on")

    with patch("pyhap.accessory_driver.AccessoryDriver.start"), patch(
        "pyhap.accessory_driver.AccessoryDriver.add_accessory"
    ), patch("homeassistant.components.homekit._LOGGER.warning") as mock_warn, patch(
        f"{PATH_HOMEKIT}.show_setup_message"
    ):
        await homekit.async_start()
        await hass.async_block_till_done()
        assert mock_warn.called is True


async def test_homekit_finds_linked_batteries(
    hass, hk_driver, debounce_patcher, device_reg, entity_reg
):
    """Test HomeKit start method."""
    entry = await async_init_integration(hass)

    homekit = HomeKit(
        hass,
        None,
        None,
        None,
        {},
        {"light.demo": {}},
        DEFAULT_SAFE_MODE,
        advertise_ip=None,
        interface_choice=None,
        entry_id=entry.entry_id,
    )
    homekit.driver = hk_driver
    homekit._filter = Mock(return_value=True)
    homekit.bridge = HomeBridge(hass, hk_driver, "mock_bridge")

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    binary_charging_sensor = entity_reg.async_get_or_create(
        "binary_sensor",
        "light",
        "battery_charging",
        device_id=device_entry.id,
        device_class=DEVICE_CLASS_BATTERY_CHARGING,
    )
    battery_sensor = entity_reg.async_get_or_create(
        "sensor",
        "light",
        "battery",
        device_id=device_entry.id,
        device_class=DEVICE_CLASS_BATTERY,
    )
    light = entity_reg.async_get_or_create(
        "light", "light", "demo", device_id=device_entry.id
    )

    hass.states.async_set(
        binary_charging_sensor.entity_id,
        STATE_ON,
        {ATTR_DEVICE_CLASS: DEVICE_CLASS_BATTERY_CHARGING},
    )
    hass.states.async_set(
        battery_sensor.entity_id, 30, {ATTR_DEVICE_CLASS: DEVICE_CLASS_BATTERY}
    )
    hass.states.async_set(light.entity_id, STATE_ON)

    def _mock_get_accessory(*args, **kwargs):
        return [None, "acc", None]

    with patch.object(homekit.bridge, "add_accessory"), patch(
        f"{PATH_HOMEKIT}.show_setup_message"
    ), patch(f"{PATH_HOMEKIT}.get_accessory") as mock_get_acc, patch(
        "pyhap.accessory_driver.AccessoryDriver.start"
    ):
        await homekit.async_start()
    await hass.async_block_till_done()

    mock_get_acc.assert_called_with(
        hass,
        hk_driver,
        ANY,
        ANY,
        {
            "linked_battery_charging_sensor": "binary_sensor.light_battery_charging",
            "linked_battery_sensor": "sensor.light_battery",
        },
    )


async def test_setup_imported(hass):
    """Test async_setup with imported config options."""
    legacy_persist_file_path = hass.config.path(HOMEKIT_FILE)
    legacy_aid_storage_path = hass.config.path(STORAGE_DIR, "homekit.aids")
    legacy_homekit_state_contents = {"homekit.state": 1}
    legacy_homekit_aids_contents = {"homekit.aids": 1}
    await hass.async_add_executor_job(
        _write_data, legacy_persist_file_path, legacy_homekit_state_contents
    )
    await hass.async_add_executor_job(
        _write_data, legacy_aid_storage_path, legacy_homekit_aids_contents
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_IMPORT,
        data={CONF_NAME: BRIDGE_NAME, CONF_PORT: DEFAULT_PORT, CONF_ENTRY_INDEX: 0},
        options={},
    )
    entry.add_to_hass(hass)

    with patch(f"{PATH_HOMEKIT}.HomeKit") as mock_homekit:
        mock_homekit.return_value = homekit = Mock()
        type(homekit).async_start = AsyncMock()
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    mock_homekit.assert_any_call(
        hass,
        BRIDGE_NAME,
        DEFAULT_PORT,
        None,
        ANY,
        {},
        DEFAULT_SAFE_MODE,
        None,
        None,
        entry.entry_id,
    )
    assert mock_homekit().setup.called is True

    # Test auto start enabled
    mock_homekit.reset_mock()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    mock_homekit().async_start.assert_called()

    migrated_persist_file_path = get_persist_fullpath_for_entry_id(hass, entry.entry_id)
    assert (
        await hass.async_add_executor_job(
            json_util.load_json, migrated_persist_file_path
        )
        == legacy_homekit_state_contents
    )
    os.unlink(migrated_persist_file_path)
    migrated_aid_file_path = get_aid_storage_fullpath_for_entry_id(hass, entry.entry_id)
    assert (
        await hass.async_add_executor_job(json_util.load_json, migrated_aid_file_path)
        == legacy_homekit_aids_contents
    )
    os.unlink(migrated_aid_file_path)


async def test_yaml_updates_update_config_entry_for_name(hass):
    """Test async_setup with imported config."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_IMPORT,
        data={CONF_NAME: BRIDGE_NAME, CONF_PORT: DEFAULT_PORT},
        options={},
    )
    entry.add_to_hass(hass)

    with patch(f"{PATH_HOMEKIT}.HomeKit") as mock_homekit:
        mock_homekit.return_value = homekit = Mock()
        type(homekit).async_start = AsyncMock()
        assert await async_setup_component(
            hass, "homekit", {"homekit": {CONF_NAME: BRIDGE_NAME, CONF_PORT: 12345}}
        )
        await hass.async_block_till_done()

    mock_homekit.assert_any_call(
        hass,
        BRIDGE_NAME,
        12345,
        None,
        ANY,
        {},
        DEFAULT_SAFE_MODE,
        None,
        None,
        entry.entry_id,
    )
    assert mock_homekit().setup.called is True

    # Test auto start enabled
    mock_homekit.reset_mock()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    mock_homekit().async_start.assert_called()


async def test_raise_config_entry_not_ready(hass):
    """Test async_setup when the port is not available."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: BRIDGE_NAME, CONF_PORT: DEFAULT_PORT},
        options={},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homekit.port_is_available", return_value=False,
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


def _write_data(path: str, data: Dict) -> None:
    """Write the data."""
    if not os.path.isdir(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    json_util.save_json(path, data)
