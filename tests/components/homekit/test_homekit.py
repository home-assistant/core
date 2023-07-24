"""Tests for the HomeKit component."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock, Mock, patch
from uuid import uuid1

from pyhap.accessory import Accessory
from pyhap.const import CATEGORY_CAMERA, CATEGORY_TELEVISION
import pytest

from homeassistant import config as hass_config
from homeassistant.components import homekit as homekit_base, zeroconf
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
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
    BRIDGE_NAME,
    BRIDGE_SERIAL_NUMBER,
    CONF_ADVERTISE_IP,
    DEFAULT_PORT,
    DOMAIN,
    HOMEKIT,
    HOMEKIT_MODE_ACCESSORY,
    HOMEKIT_MODE_BRIDGE,
    SERVICE_HOMEKIT_RESET_ACCESSORY,
    SERVICE_HOMEKIT_UNPAIR,
)
from homeassistant.components.homekit.type_triggers import DeviceTriggerAccessory
from homeassistant.components.homekit.util import get_persist_fullpath_for_entry_id
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_ZEROCONF
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME,
    CONF_PORT,
    EVENT_HOMEASSISTANT_STARTED,
    PERCENTAGE,
    SERVICE_RELOAD,
    STATE_ON,
    EntityCategory,
)
from homeassistant.core import HomeAssistant, HomeAssistantError, State
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    instance_id,
)
from homeassistant.helpers.entityfilter import (
    CONF_EXCLUDE_DOMAINS,
    CONF_EXCLUDE_ENTITIES,
    CONF_EXCLUDE_ENTITY_GLOBS,
    CONF_INCLUDE_DOMAINS,
    CONF_INCLUDE_ENTITIES,
    CONF_INCLUDE_ENTITY_GLOBS,
    convert_filter,
)
from homeassistant.setup import async_setup_component

from .util import PATH_HOMEKIT, async_init_entry, async_init_integration

from tests.common import MockConfigEntry, get_fixture_path

IP_ADDRESS = "127.0.0.1"


def generate_filter(
    include_domains,
    include_entities,
    exclude_domains,
    exclude_entites,
    include_globs=None,
    exclude_globs=None,
):
    """Generate an entity filter using the standard method."""
    return convert_filter(
        {
            CONF_INCLUDE_DOMAINS: include_domains,
            CONF_INCLUDE_ENTITIES: include_entities,
            CONF_EXCLUDE_DOMAINS: exclude_domains,
            CONF_EXCLUDE_ENTITIES: exclude_entites,
            CONF_INCLUDE_ENTITY_GLOBS: include_globs or [],
            CONF_EXCLUDE_ENTITY_GLOBS: exclude_globs or [],
        }
    )


@pytest.fixture(autouse=True)
def always_patch_driver(hk_driver):
    """Load the hk_driver fixture."""


@pytest.fixture(autouse=True)
def patch_source_ip(mock_get_source_ip):
    """Patch homeassistant and pyhap functions for getting local address."""
    with patch("pyhap.util.get_local_address", return_value="10.10.10.10"):
        yield


def _mock_homekit(hass, entry, homekit_mode, entity_filter=None, devices=None):
    return HomeKit(
        hass=hass,
        name=BRIDGE_NAME,
        port=DEFAULT_PORT,
        ip_address=None,
        entity_filter=entity_filter or generate_filter([], [], [], []),
        exclude_accessory_mode=False,
        entity_config={},
        homekit_mode=homekit_mode,
        advertise_ips=None,
        entry_id=entry.entry_id,
        entry_title=entry.title,
        devices=devices,
    )


def _mock_homekit_bridge(hass, entry):
    homekit = _mock_homekit(hass, entry, HOMEKIT_MODE_BRIDGE)
    homekit.driver = MagicMock()
    homekit.iid_storage = MagicMock()
    return homekit


def _mock_accessories(accessory_count):
    accessories = {}
    for idx in range(accessory_count + 1):
        accessories[idx + 1000] = MagicMock(async_stop=AsyncMock())
    return accessories


def _mock_pyhap_bridge():
    return MagicMock(
        aid=1, accessories=_mock_accessories(10), display_name="HomeKit Bridge"
    )


async def test_setup_min(hass: HomeAssistant, mock_async_zeroconf: None) -> None:
    """Test async_setup with min config options."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: BRIDGE_NAME, CONF_PORT: DEFAULT_PORT},
        options={},
    )
    entry.add_to_hass(hass)

    with patch(f"{PATH_HOMEKIT}.HomeKit") as mock_homekit, patch(
        "homeassistant.components.network.async_get_source_ip", return_value="1.2.3.4"
    ):
        mock_homekit.return_value = homekit = Mock()
        type(homekit).async_start = AsyncMock()
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    mock_homekit.assert_any_call(
        hass,
        BRIDGE_NAME,
        DEFAULT_PORT,
        [None],
        ANY,
        ANY,
        {},
        HOMEKIT_MODE_BRIDGE,
        ["1.2.3.4", "10.10.10.10"],
        entry.entry_id,
        entry.title,
        devices=[],
    )

    # Test auto start enabled
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    assert mock_homekit().async_start.called is True


@patch(f"{PATH_HOMEKIT}.async_port_is_available", return_value=True)
async def test_removing_entry(
    port_mock, hass: HomeAssistant, mock_async_zeroconf: None
) -> None:
    """Test removing a config entry."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: BRIDGE_NAME, CONF_PORT: DEFAULT_PORT},
        options={},
    )
    entry.add_to_hass(hass)

    with patch(f"{PATH_HOMEKIT}.HomeKit") as mock_homekit, patch(
        "homeassistant.components.network.async_get_source_ip", return_value="1.2.3.4"
    ):
        mock_homekit.return_value = homekit = Mock()
        type(homekit).async_start = AsyncMock()
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    mock_homekit.assert_any_call(
        hass,
        BRIDGE_NAME,
        DEFAULT_PORT,
        [None],
        ANY,
        ANY,
        {},
        HOMEKIT_MODE_BRIDGE,
        ["1.2.3.4", "10.10.10.10"],
        entry.entry_id,
        entry.title,
        devices=[],
    )

    # Test auto start enabled
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    assert mock_homekit().async_start.called is True

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()


async def test_homekit_setup(
    hass: HomeAssistant, hk_driver, mock_async_zeroconf: None
) -> None:
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
        IP_ADDRESS,
        True,
        {},
        {},
        HOMEKIT_MODE_BRIDGE,
        advertise_ips=None,
        entry_id=entry.entry_id,
        entry_title=entry.title,
    )

    hass.states.async_set("light.demo", "on")
    hass.states.async_set("light.demo2", "on")
    zeroconf_mock = MagicMock()
    uuid = await instance_id.async_get(hass)
    with patch(f"{PATH_HOMEKIT}.HomeDriver", return_value=hk_driver) as mock_driver:
        homekit.iid_storage = MagicMock()
        await hass.async_add_executor_job(homekit.setup, zeroconf_mock, uuid)

    path = get_persist_fullpath_for_entry_id(hass, entry.entry_id)
    mock_driver.assert_called_with(
        hass,
        entry.entry_id,
        BRIDGE_NAME,
        entry.title,
        loop=hass.loop,
        address=IP_ADDRESS,
        port=DEFAULT_PORT,
        persist_file=path,
        advertised_address=None,
        async_zeroconf_instance=zeroconf_mock,
        zeroconf_server=f"{uuid}-hap.local.",
        loader=ANY,
        iid_storage=ANY,
    )
    assert homekit.driver.safe_mode is False


async def test_homekit_setup_ip_address(
    hass: HomeAssistant, hk_driver, mock_async_zeroconf: None
) -> None:
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
        True,
        {},
        {},
        HOMEKIT_MODE_BRIDGE,
        None,
        entry_id=entry.entry_id,
        entry_title=entry.title,
    )

    path = get_persist_fullpath_for_entry_id(hass, entry.entry_id)
    uuid = await instance_id.async_get(hass)
    with patch(f"{PATH_HOMEKIT}.HomeDriver", return_value=hk_driver) as mock_driver:
        homekit.iid_storage = MagicMock()
        await hass.async_add_executor_job(homekit.setup, mock_async_zeroconf, uuid)
    mock_driver.assert_called_with(
        hass,
        entry.entry_id,
        BRIDGE_NAME,
        entry.title,
        loop=hass.loop,
        address="172.0.0.0",
        port=DEFAULT_PORT,
        persist_file=path,
        advertised_address=None,
        async_zeroconf_instance=mock_async_zeroconf,
        zeroconf_server=f"{uuid}-hap.local.",
        loader=ANY,
        iid_storage=ANY,
    )


async def test_homekit_with_single_advertise_ips(
    hass: HomeAssistant,
    hk_driver,
    mock_async_zeroconf: None,
    hass_storage: dict[str, Any],
) -> None:
    """Test setup with a single advertise ips."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: "mock_name", CONF_PORT: 12345, CONF_ADVERTISE_IP: "1.3.4.4"},
        source=SOURCE_IMPORT,
    )
    entry.add_to_hass(hass)
    with patch(f"{PATH_HOMEKIT}.HomeDriver", return_value=hk_driver) as mock_driver:
        mock_driver.async_start = AsyncMock()
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    mock_driver.assert_called_with(
        hass,
        entry.entry_id,
        ANY,
        entry.title,
        loop=hass.loop,
        address=[None],
        port=ANY,
        persist_file=ANY,
        advertised_address="1.3.4.4",
        async_zeroconf_instance=mock_async_zeroconf,
        zeroconf_server=ANY,
        loader=ANY,
        iid_storage=ANY,
    )


async def test_homekit_with_many_advertise_ips(
    hass: HomeAssistant,
    hk_driver,
    mock_async_zeroconf: None,
    hass_storage: dict[str, Any],
) -> None:
    """Test setup with many advertise ips."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_NAME: "mock_name",
            CONF_PORT: 12345,
            CONF_ADVERTISE_IP: ["1.3.4.4", "4.3.2.2"],
        },
        source=SOURCE_IMPORT,
    )
    entry.add_to_hass(hass)
    with patch(f"{PATH_HOMEKIT}.HomeDriver", return_value=hk_driver) as mock_driver:
        mock_driver.async_start = AsyncMock()
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    mock_driver.assert_called_with(
        hass,
        entry.entry_id,
        ANY,
        entry.title,
        loop=hass.loop,
        address=[None],
        port=ANY,
        persist_file=ANY,
        advertised_address=["1.3.4.4", "4.3.2.2"],
        async_zeroconf_instance=mock_async_zeroconf,
        zeroconf_server=ANY,
        loader=ANY,
        iid_storage=ANY,
    )


async def test_homekit_setup_advertise_ips(
    hass: HomeAssistant, hk_driver, mock_async_zeroconf: None
) -> None:
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
        True,
        {},
        {},
        HOMEKIT_MODE_BRIDGE,
        "192.168.1.100",
        entry_id=entry.entry_id,
        entry_title=entry.title,
    )

    async_zeroconf_instance = MagicMock()
    path = get_persist_fullpath_for_entry_id(hass, entry.entry_id)
    uuid = await instance_id.async_get(hass)
    with patch(f"{PATH_HOMEKIT}.HomeDriver", return_value=hk_driver) as mock_driver:
        homekit.iid_storage = MagicMock()
        await hass.async_add_executor_job(homekit.setup, async_zeroconf_instance, uuid)
    mock_driver.assert_called_with(
        hass,
        entry.entry_id,
        BRIDGE_NAME,
        entry.title,
        loop=hass.loop,
        address="0.0.0.0",
        port=DEFAULT_PORT,
        persist_file=path,
        advertised_address="192.168.1.100",
        async_zeroconf_instance=async_zeroconf_instance,
        zeroconf_server=f"{uuid}-hap.local.",
        loader=ANY,
        iid_storage=ANY,
    )


async def test_homekit_add_accessory(
    hass: HomeAssistant, mock_async_zeroconf: None, mock_hap
) -> None:
    """Add accessory if config exists and get_acc returns an accessory."""

    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entry.add_to_hass(hass)

    homekit = _mock_homekit_bridge(hass, entry)
    mock_acc = Mock(category="any")

    with patch(f"{PATH_HOMEKIT}.HomeKit", return_value=homekit):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    homekit.bridge = _mock_pyhap_bridge()

    with patch(f"{PATH_HOMEKIT}.get_accessory") as mock_get_acc:
        mock_get_acc.side_effect = [None, mock_acc, None]
        state = State("light.demo", "on")
        homekit.add_bridge_accessory(state)
        mock_get_acc.assert_called_with(hass, ANY, ANY, 1403373688, {})
        assert not homekit.bridge.add_accessory.called

        state = State("demo.test", "on")
        homekit.add_bridge_accessory(state)
        mock_get_acc.assert_called_with(hass, ANY, ANY, 600325356, {})
        assert homekit.bridge.add_accessory.called

        state = State("demo.test_2", "on")
        homekit.add_bridge_accessory(state)
        mock_get_acc.assert_called_with(hass, ANY, ANY, 1467253281, {})
        assert homekit.bridge.add_accessory.called

        await homekit.async_stop()


@pytest.mark.parametrize("acc_category", [CATEGORY_TELEVISION, CATEGORY_CAMERA])
async def test_homekit_warn_add_accessory_bridge(
    hass: HomeAssistant,
    acc_category,
    mock_async_zeroconf: None,
    mock_hap,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test we warn when adding cameras or tvs to a bridge."""

    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entry.add_to_hass(hass)

    homekit = _mock_homekit_bridge(hass, entry)

    with patch(f"{PATH_HOMEKIT}.HomeKit", return_value=homekit):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    mock_camera_acc = Mock(category=acc_category)
    homekit.bridge = _mock_pyhap_bridge()

    with patch(f"{PATH_HOMEKIT}.get_accessory") as mock_get_acc:
        mock_get_acc.side_effect = [None, mock_camera_acc, None]
        state = State("camera.test", "on")
        homekit.add_bridge_accessory(state)
        mock_get_acc.assert_called_with(hass, ANY, ANY, 1508819236, {})
        assert not homekit.bridge.add_accessory.called
        await homekit.async_stop()

    assert "accessory mode" in caplog.text


async def test_homekit_remove_accessory(
    hass: HomeAssistant, mock_async_zeroconf: None
) -> None:
    """Remove accessory from bridge."""
    entry = await async_init_integration(hass)

    homekit = _mock_homekit(hass, entry, HOMEKIT_MODE_BRIDGE)

    homekit.driver = "driver"
    homekit.bridge = _mock_pyhap_bridge()
    acc_mock = MagicMock()
    acc_mock.stop = AsyncMock()
    homekit.bridge.accessories = {6: acc_mock}

    acc = await homekit.async_remove_bridge_accessory(6)
    assert acc is acc_mock
    assert len(homekit.bridge.accessories) == 0


async def test_homekit_entity_filter(
    hass: HomeAssistant, mock_async_zeroconf: None
) -> None:
    """Test the entity filter."""
    entry = await async_init_integration(hass)

    entity_filter = generate_filter(["cover"], ["demo.test"], [], [])
    homekit = _mock_homekit(hass, entry, HOMEKIT_MODE_BRIDGE, entity_filter)

    homekit.bridge = Mock()
    homekit.bridge.accessories = {}
    hass.states.async_set("cover.test", "open")
    hass.states.async_set("demo.test", "on")
    hass.states.async_set("light.demo", "on")

    filtered_states = await homekit.async_configure_accessories()
    assert hass.states.get("cover.test") in filtered_states
    assert hass.states.get("demo.test") in filtered_states
    assert hass.states.get("light.demo") not in filtered_states


async def test_homekit_entity_glob_filter(
    hass: HomeAssistant, mock_async_zeroconf: None
) -> None:
    """Test the entity filter."""
    entry = await async_init_integration(hass)

    entity_filter = generate_filter(
        ["cover"], ["demo.test"], [], [], ["*.included_*"], ["*.excluded_*"]
    )
    homekit = _mock_homekit(hass, entry, HOMEKIT_MODE_BRIDGE, entity_filter)

    homekit.bridge = Mock()
    homekit.bridge.accessories = {}

    hass.states.async_set("cover.test", "open")
    hass.states.async_set("demo.test", "on")
    hass.states.async_set("cover.excluded_test", "open")
    hass.states.async_set("light.included_test", "on")

    filtered_states = await homekit.async_configure_accessories()
    assert hass.states.get("cover.test") in filtered_states
    assert hass.states.get("demo.test") in filtered_states
    assert hass.states.get("cover.excluded_test") not in filtered_states
    assert hass.states.get("light.included_test") in filtered_states


async def test_homekit_entity_glob_filter_with_config_entities(
    hass: HomeAssistant, mock_async_zeroconf: None, entity_registry: er.EntityRegistry
) -> None:
    """Test the entity filter with configuration entities."""
    entry = await async_init_integration(hass)

    select_config_entity = entity_registry.async_get_or_create(
        "select",
        "any",
        "any",
        device_id="1234",
        entity_category=EntityCategory.CONFIG,
    )
    hass.states.async_set(select_config_entity.entity_id, "off")

    switch_config_entity = entity_registry.async_get_or_create(
        "switch",
        "any",
        "any",
        device_id="1234",
        entity_category=EntityCategory.CONFIG,
    )
    hass.states.async_set(switch_config_entity.entity_id, "off")
    hass.states.async_set("select.keep", "open")

    hass.states.async_set("cover.excluded_test", "open")
    hass.states.async_set("light.included_test", "on")

    entity_filter = generate_filter(
        ["select"],
        ["switch.test", switch_config_entity.entity_id],
        [],
        [],
        ["*.included_*"],
        ["*.excluded_*"],
    )
    homekit = _mock_homekit(hass, entry, HOMEKIT_MODE_BRIDGE, entity_filter)

    homekit.bridge = Mock()
    homekit.bridge.accessories = {}

    filtered_states = await homekit.async_configure_accessories()
    assert (
        hass.states.get(switch_config_entity.entity_id) in filtered_states
    )  # explicitly included
    assert (
        hass.states.get(select_config_entity.entity_id) not in filtered_states
    )  # not explicted included and its a config entity
    assert hass.states.get("cover.excluded_test") not in filtered_states
    assert hass.states.get("light.included_test") in filtered_states
    assert hass.states.get("select.keep") in filtered_states


async def test_homekit_entity_glob_filter_with_hidden_entities(
    hass: HomeAssistant, mock_async_zeroconf: None, entity_registry: er.EntityRegistry
) -> None:
    """Test the entity filter with hidden entities."""
    entry = await async_init_integration(hass)

    select_config_entity = entity_registry.async_get_or_create(
        "select",
        "any",
        "any",
        device_id="1234",
        hidden_by=er.RegistryEntryHider.INTEGRATION,
    )
    hass.states.async_set(select_config_entity.entity_id, "off")

    switch_config_entity = entity_registry.async_get_or_create(
        "switch",
        "any",
        "any",
        device_id="1234",
        hidden_by=er.RegistryEntryHider.INTEGRATION,
    )
    hass.states.async_set(switch_config_entity.entity_id, "off")
    hass.states.async_set("select.keep", "open")

    hass.states.async_set("cover.excluded_test", "open")
    hass.states.async_set("light.included_test", "on")

    entity_filter = generate_filter(
        ["select"],
        ["switch.test", switch_config_entity.entity_id],
        [],
        [],
        ["*.included_*"],
        ["*.excluded_*"],
    )
    homekit = _mock_homekit(hass, entry, HOMEKIT_MODE_BRIDGE, entity_filter)

    homekit.bridge = Mock()
    homekit.bridge.accessories = {}

    filtered_states = await homekit.async_configure_accessories()
    assert (
        hass.states.get(switch_config_entity.entity_id) in filtered_states
    )  # explicitly included
    assert (
        hass.states.get(select_config_entity.entity_id) not in filtered_states
    )  # not explicted included and its a hidden entity
    assert hass.states.get("cover.excluded_test") not in filtered_states
    assert hass.states.get("light.included_test") in filtered_states
    assert hass.states.get("select.keep") in filtered_states


async def test_homekit_start(
    hass: HomeAssistant,
    hk_driver,
    mock_async_zeroconf: None,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test HomeKit start method."""
    entry = await async_init_integration(hass)

    homekit = _mock_homekit(hass, entry, HOMEKIT_MODE_BRIDGE)

    homekit.bridge = Mock()
    homekit.bridge.accessories = []
    homekit.driver = hk_driver
    acc = Accessory(hk_driver, "any")
    homekit.driver.accessory = acc

    connection = (dr.CONNECTION_NETWORK_MAC, "AA:BB:CC:DD:EE:FF")
    bridge_with_wrong_mac = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={connection},
        manufacturer="Any",
        name="Any",
        model="Home Assistant HomeKit Bridge",
    )

    hass.states.async_set("light.demo", "on")
    hass.states.async_set("light.demo2", "on")
    state = hass.states.async_all()[0]

    with patch(f"{PATH_HOMEKIT}.HomeKit.add_bridge_accessory") as mock_add_acc, patch(
        f"{PATH_HOMEKIT}.async_show_setup_message"
    ) as mock_setup_msg, patch(
        "pyhap.accessory_driver.AccessoryDriver.async_start"
    ) as hk_driver_start:
        await homekit.async_start()

    await hass.async_block_till_done()
    mock_add_acc.assert_any_call(state)
    mock_setup_msg.assert_called_with(
        hass, entry.entry_id, "Mock Title (Home Assistant Bridge)", ANY, ANY
    )
    assert hk_driver_start.called
    assert homekit.status == STATUS_RUNNING

    # Test start() if already started
    hk_driver_start.reset_mock()
    await homekit.async_start()
    await hass.async_block_till_done()
    assert not hk_driver_start.called

    assert device_registry.async_get(bridge_with_wrong_mac.id) is None

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, entry.entry_id, BRIDGE_SERIAL_NUMBER)}
    )
    assert device
    formatted_mac = dr.format_mac(homekit.driver.state.mac)
    assert (dr.CONNECTION_NETWORK_MAC, formatted_mac) in device.connections

    # Start again to make sure the registry entry is kept
    homekit.status = STATUS_READY
    with patch(f"{PATH_HOMEKIT}.HomeKit.add_bridge_accessory") as mock_add_acc, patch(
        f"{PATH_HOMEKIT}.async_show_setup_message"
    ) as mock_setup_msg, patch(
        "pyhap.accessory_driver.AccessoryDriver.async_start"
    ) as hk_driver_start:
        await homekit.async_start()

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, entry.entry_id, BRIDGE_SERIAL_NUMBER)}
    )
    assert device
    formatted_mac = dr.format_mac(homekit.driver.state.mac)
    assert (dr.CONNECTION_NETWORK_MAC, formatted_mac) in device.connections

    assert len(device_registry.devices) == 1
    assert homekit.driver.state.config_version == 1


async def test_homekit_start_with_a_broken_accessory(
    hass: HomeAssistant, hk_driver, mock_async_zeroconf: None
) -> None:
    """Test HomeKit start method."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entity_filter = generate_filter(["cover", "light"], ["demo.test"], [], [])

    await async_init_entry(hass, entry)
    homekit = _mock_homekit(hass, entry, HOMEKIT_MODE_BRIDGE, entity_filter)

    homekit.bridge = Mock()
    homekit.bridge.accessories = []
    homekit.driver = hk_driver
    homekit.driver.accessory = Accessory(hk_driver, "any")

    hass.states.async_set("light.demo", "on")
    hass.states.async_set("light.broken", "on")

    with patch(f"{PATH_HOMEKIT}.get_accessory", side_effect=Exception), patch(
        f"{PATH_HOMEKIT}.async_show_setup_message"
    ) as mock_setup_msg, patch(
        "pyhap.accessory_driver.AccessoryDriver.async_start"
    ) as hk_driver_start:
        await homekit.async_start()

    await hass.async_block_till_done()
    mock_setup_msg.assert_called_with(
        hass, entry.entry_id, "Mock Title (Home Assistant Bridge)", ANY, ANY
    )
    assert hk_driver_start.called
    assert homekit.status == STATUS_RUNNING

    # Test start() if already started
    hk_driver_start.reset_mock()
    await homekit.async_start()
    await hass.async_block_till_done()
    assert not hk_driver_start.called


async def test_homekit_start_with_a_device(
    hass: HomeAssistant,
    hk_driver,
    mock_async_zeroconf: None,
    demo_cleanup,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test HomeKit start method with a device."""

    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "demo", {"demo": {}})
    await hass.async_block_till_done()

    reg_entry = entity_registry.async_get("light.ceiling_lights")
    assert reg_entry is not None
    device_id = reg_entry.device_id
    await async_init_entry(hass, entry)
    homekit = _mock_homekit(hass, entry, HOMEKIT_MODE_BRIDGE, None, devices=[device_id])
    homekit.driver = hk_driver

    with patch(f"{PATH_HOMEKIT}.get_accessory", side_effect=Exception), patch(
        f"{PATH_HOMEKIT}.async_show_setup_message"
    ) as mock_setup_msg:
        await homekit.async_start()

    await hass.async_block_till_done()
    mock_setup_msg.assert_called_with(
        hass, entry.entry_id, "Mock Title (Home Assistant Bridge)", ANY, ANY
    )
    assert homekit.status == STATUS_RUNNING

    assert isinstance(
        list(homekit.driver.accessory.accessories.values())[0], DeviceTriggerAccessory
    )
    await homekit.async_stop()


async def test_homekit_stop(hass: HomeAssistant) -> None:
    """Test HomeKit stop method."""
    entry = await async_init_integration(hass)
    homekit = _mock_homekit(hass, entry, HOMEKIT_MODE_BRIDGE)

    homekit.driver = Mock()
    homekit.driver.async_stop = AsyncMock()
    homekit.bridge = Mock()
    homekit.bridge.accessories = {}

    assert homekit.status == STATUS_READY
    await homekit.async_stop()
    await hass.async_block_till_done()
    homekit.status = STATUS_WAIT
    await homekit.async_stop()
    await hass.async_block_till_done()
    homekit.status = STATUS_STOPPED
    await homekit.async_stop()
    await hass.async_block_till_done()
    assert homekit.driver.async_stop.called is False

    # Test if driver is started
    homekit.status = STATUS_RUNNING
    await homekit.async_stop()
    await hass.async_block_till_done()
    assert homekit.driver.async_stop.called is True


async def test_homekit_reset_accessories(
    hass: HomeAssistant, mock_async_zeroconf: None, mock_hap
) -> None:
    """Test resetting HomeKit accessories."""

    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entity_id = "light.demo"
    hass.states.async_set("light.demo", "on")
    homekit = _mock_homekit(hass, entry, HOMEKIT_MODE_BRIDGE)

    with patch(f"{PATH_HOMEKIT}.HomeKit", return_value=homekit), patch(
        "pyhap.accessory_driver.AccessoryDriver.config_changed"
    ), patch("pyhap.accessory_driver.AccessoryDriver.async_start"), patch(
        f"{PATH_HOMEKIT}.accessories.HomeAccessory.run"
    ) as mock_run_accessory, patch.object(
        homekit_base, "_HOMEKIT_CONFIG_UPDATE_TIME", 0
    ):
        await async_init_entry(hass, entry)

        homekit.status = STATUS_RUNNING
        homekit.driver.aio_stop_event = MagicMock()

        await hass.services.async_call(
            DOMAIN,
            SERVICE_HOMEKIT_RESET_ACCESSORY,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()
        await hass.async_block_till_done()

        assert mock_run_accessory.called
        homekit.status = STATUS_READY
        await homekit.async_stop()


async def test_homekit_unpair(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, mock_async_zeroconf: None
) -> None:
    """Test unpairing HomeKit accessories."""

    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entity_id = "light.demo"
    hass.states.async_set("light.demo", "on")
    homekit = _mock_homekit(hass, entry, HOMEKIT_MODE_BRIDGE)

    with patch(f"{PATH_HOMEKIT}.HomeKit", return_value=homekit), patch(
        "pyhap.accessory_driver.AccessoryDriver.async_start"
    ):
        await async_init_entry(hass, entry)

        acc_mock = MagicMock()
        acc_mock.entity_id = entity_id
        acc_mock.stop = AsyncMock()

        aid = homekit.aid_storage.get_or_allocate_aid_for_entity_id(entity_id)
        homekit.bridge.accessories = {aid: acc_mock}
        homekit.status = STATUS_RUNNING
        homekit.driver.aio_stop_event = MagicMock()

        state = homekit.driver.state
        state.add_paired_client(str(uuid1()).encode("utf-8"), "any", b"1")
        state.add_paired_client(str(uuid1()).encode("utf-8"), "any", b"0")
        state.add_paired_client(str(uuid1()).encode("utf-8"), "any", b"1")
        state.add_paired_client(str(uuid1()).encode("utf-8"), "any", b"0")
        state.add_paired_client(str(uuid1()).encode("utf-8"), "any", b"0")

        formatted_mac = dr.format_mac(state.mac)
        hk_bridge_dev = device_registry.async_get_device(
            connections={(dr.CONNECTION_NETWORK_MAC, formatted_mac)}
        )

        await hass.services.async_call(
            DOMAIN,
            SERVICE_HOMEKIT_UNPAIR,
            {ATTR_DEVICE_ID: hk_bridge_dev.id},
            blocking=True,
        )
        await hass.async_block_till_done()
        assert state.paired_clients == {}
        homekit.status = STATUS_STOPPED


async def test_homekit_unpair_missing_device_id(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, mock_async_zeroconf: None
) -> None:
    """Test unpairing HomeKit accessories with invalid device id."""

    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entity_id = "light.demo"
    hass.states.async_set("light.demo", "on")
    homekit = _mock_homekit(hass, entry, HOMEKIT_MODE_BRIDGE)

    with patch(f"{PATH_HOMEKIT}.HomeKit", return_value=homekit), patch(
        "pyhap.accessory_driver.AccessoryDriver.async_start"
    ):
        await async_init_entry(hass, entry)

        acc_mock = MagicMock()
        acc_mock.entity_id = entity_id
        acc_mock.stop = AsyncMock()

        aid = homekit.aid_storage.get_or_allocate_aid_for_entity_id(entity_id)
        homekit.bridge.accessories = {aid: acc_mock}
        homekit.status = STATUS_RUNNING
        homekit.driver.aio_stop_event = MagicMock()

        state = homekit.driver.state
        client_1 = str(uuid1()).encode("utf-8")
        state.add_paired_client(client_1, "any", b"1")
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_HOMEKIT_UNPAIR,
                {ATTR_DEVICE_ID: "notvalid"},
                blocking=True,
            )
        await hass.async_block_till_done()
        state.paired_clients = {client_1.decode("utf-8"): "any"}
        homekit.status = STATUS_STOPPED


async def test_homekit_unpair_not_homekit_device(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, mock_async_zeroconf: None
) -> None:
    """Test unpairing HomeKit accessories with a non-homekit device id."""

    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    not_homekit_entry = MockConfigEntry(
        domain="not_homekit", data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entity_id = "light.demo"
    hass.states.async_set("light.demo", "on")
    homekit = _mock_homekit(hass, entry, HOMEKIT_MODE_BRIDGE)

    with patch(f"{PATH_HOMEKIT}.HomeKit", return_value=homekit), patch(
        "pyhap.accessory_driver.AccessoryDriver.async_start"
    ):
        await async_init_entry(hass, entry)

        acc_mock = MagicMock()
        acc_mock.entity_id = entity_id
        acc_mock.stop = AsyncMock()

        aid = homekit.aid_storage.get_or_allocate_aid_for_entity_id(entity_id)
        homekit.bridge.accessories = {aid: acc_mock}
        homekit.status = STATUS_RUNNING

        device_entry = device_registry.async_get_or_create(
            config_entry_id=not_homekit_entry.entry_id,
            sw_version="0.16.0",
            model="Powerwall 2",
            manufacturer="Tesla",
            connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        )

        state = homekit.driver.state
        client_1 = str(uuid1()).encode("utf-8")
        state.add_paired_client(client_1, "any", b"1")
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_HOMEKIT_UNPAIR,
                {ATTR_DEVICE_ID: device_entry.id},
                blocking=True,
            )
        await hass.async_block_till_done()
        state.paired_clients = {client_1.decode("utf-8"): "any"}
        homekit.status = STATUS_STOPPED


async def test_homekit_reset_accessories_not_supported(
    hass: HomeAssistant, mock_async_zeroconf: None
) -> None:
    """Test resetting HomeKit accessories with an unsupported entity."""

    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entity_id = "not_supported.demo"
    hass.states.async_set("not_supported.demo", "on")
    homekit = _mock_homekit(hass, entry, HOMEKIT_MODE_BRIDGE)

    with patch(f"{PATH_HOMEKIT}.HomeKit", return_value=homekit), patch(
        "pyhap.accessory.Bridge.add_accessory"
    ) as mock_add_accessory, patch(
        "pyhap.accessory_driver.AccessoryDriver.config_changed"
    ) as hk_driver_config_changed, patch(
        "pyhap.accessory_driver.AccessoryDriver.async_start"
    ), patch.object(
        homekit_base, "_HOMEKIT_CONFIG_UPDATE_TIME", 0
    ):
        await async_init_entry(hass, entry)

        acc_mock = MagicMock()
        acc_mock.entity_id = entity_id
        acc_mock.stop = AsyncMock()

        aid = homekit.aid_storage.get_or_allocate_aid_for_entity_id(entity_id)
        homekit.bridge.accessories = {aid: acc_mock}
        homekit.status = STATUS_RUNNING
        homekit.driver.aio_stop_event = MagicMock()

        await hass.services.async_call(
            DOMAIN,
            SERVICE_HOMEKIT_RESET_ACCESSORY,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert hk_driver_config_changed.call_count == 2
        assert not mock_add_accessory.called
        assert len(homekit.bridge.accessories) == 0
        homekit.status = STATUS_STOPPED


async def test_homekit_reset_accessories_state_missing(
    hass: HomeAssistant, mock_async_zeroconf: None
) -> None:
    """Test resetting HomeKit accessories when the state goes missing."""

    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entity_id = "light.demo"
    homekit = _mock_homekit(hass, entry, HOMEKIT_MODE_BRIDGE)

    with patch(f"{PATH_HOMEKIT}.HomeKit", return_value=homekit), patch(
        "pyhap.accessory.Bridge.add_accessory"
    ) as mock_add_accessory, patch(
        "pyhap.accessory_driver.AccessoryDriver.config_changed"
    ) as hk_driver_config_changed, patch(
        "pyhap.accessory_driver.AccessoryDriver.async_start"
    ), patch.object(
        homekit_base, "_HOMEKIT_CONFIG_UPDATE_TIME", 0
    ):
        await async_init_entry(hass, entry)

        acc_mock = MagicMock()
        acc_mock.entity_id = entity_id
        acc_mock.stop = AsyncMock()

        aid = homekit.aid_storage.get_or_allocate_aid_for_entity_id(entity_id)
        homekit.bridge.accessories = {aid: acc_mock}
        homekit.status = STATUS_RUNNING
        homekit.driver.aio_stop_event = MagicMock()

        await hass.services.async_call(
            DOMAIN,
            SERVICE_HOMEKIT_RESET_ACCESSORY,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert hk_driver_config_changed.call_count == 0
        assert not mock_add_accessory.called
        homekit.status = STATUS_STOPPED


async def test_homekit_reset_accessories_not_bridged(
    hass: HomeAssistant, mock_async_zeroconf: None
) -> None:
    """Test resetting HomeKit accessories when the state is not bridged."""

    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entity_id = "light.demo"
    homekit = _mock_homekit(hass, entry, HOMEKIT_MODE_BRIDGE)

    with patch(f"{PATH_HOMEKIT}.HomeKit", return_value=homekit), patch(
        "pyhap.accessory.Bridge.add_accessory"
    ) as mock_add_accessory, patch(
        "pyhap.accessory_driver.AccessoryDriver.config_changed"
    ) as hk_driver_config_changed, patch(
        "pyhap.accessory_driver.AccessoryDriver.async_start"
    ), patch.object(
        homekit_base, "_HOMEKIT_CONFIG_UPDATE_TIME", 0
    ):
        await async_init_entry(hass, entry)

        acc_mock = MagicMock()
        acc_mock.entity_id = entity_id
        acc_mock.stop = AsyncMock()

        aid = homekit.aid_storage.get_or_allocate_aid_for_entity_id(entity_id)
        homekit.bridge.accessories = {aid: acc_mock}
        homekit.status = STATUS_RUNNING
        homekit.driver.aio_stop_event = MagicMock()

        await hass.services.async_call(
            DOMAIN,
            SERVICE_HOMEKIT_RESET_ACCESSORY,
            {ATTR_ENTITY_ID: "light.not_bridged"},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert hk_driver_config_changed.call_count == 0
        assert not mock_add_accessory.called
        homekit.status = STATUS_STOPPED


async def test_homekit_reset_single_accessory(
    hass: HomeAssistant, mock_hap, mock_async_zeroconf: None
) -> None:
    """Test resetting HomeKit single accessory."""

    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entity_id = "light.demo"
    hass.states.async_set("light.demo", "on")
    homekit = _mock_homekit(hass, entry, HOMEKIT_MODE_ACCESSORY)

    with patch(f"{PATH_HOMEKIT}.HomeKit", return_value=homekit), patch(
        "pyhap.accessory_driver.AccessoryDriver.config_changed"
    ) as hk_driver_config_changed, patch(
        "pyhap.accessory_driver.AccessoryDriver.async_start"
    ), patch(
        f"{PATH_HOMEKIT}.accessories.HomeAccessory.run"
    ) as mock_run:
        await async_init_entry(hass, entry)
        homekit.status = STATUS_RUNNING
        homekit.driver.aio_stop_event = MagicMock()

        await hass.services.async_call(
            DOMAIN,
            SERVICE_HOMEKIT_RESET_ACCESSORY,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()
        assert mock_run.called
        assert hk_driver_config_changed.call_count == 1
        homekit.status = STATUS_READY
        await homekit.async_stop()


async def test_homekit_reset_single_accessory_unsupported(
    hass: HomeAssistant, mock_async_zeroconf: None
) -> None:
    """Test resetting HomeKit single accessory with an unsupported entity."""

    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entity_id = "not_supported.demo"
    hass.states.async_set("not_supported.demo", "on")
    homekit = _mock_homekit(hass, entry, HOMEKIT_MODE_ACCESSORY)

    with patch(f"{PATH_HOMEKIT}.HomeKit", return_value=homekit), patch(
        "pyhap.accessory_driver.AccessoryDriver.config_changed"
    ) as hk_driver_config_changed, patch(
        "pyhap.accessory_driver.AccessoryDriver.async_start"
    ):
        await async_init_entry(hass, entry)

        homekit.status = STATUS_RUNNING
        acc_mock = MagicMock()
        acc_mock.entity_id = entity_id
        acc_mock.stop = AsyncMock()

        homekit.driver.accessory = acc_mock
        homekit.driver.aio_stop_event = MagicMock()

        await hass.services.async_call(
            DOMAIN,
            SERVICE_HOMEKIT_RESET_ACCESSORY,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert hk_driver_config_changed.call_count == 0
        homekit.status = STATUS_STOPPED


async def test_homekit_reset_single_accessory_state_missing(
    hass: HomeAssistant, mock_async_zeroconf: None
) -> None:
    """Test resetting HomeKit single accessory when the state goes missing."""

    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entity_id = "light.demo"
    homekit = _mock_homekit(hass, entry, HOMEKIT_MODE_ACCESSORY)

    with patch(f"{PATH_HOMEKIT}.HomeKit", return_value=homekit), patch(
        "pyhap.accessory_driver.AccessoryDriver.config_changed"
    ) as hk_driver_config_changed, patch(
        "pyhap.accessory_driver.AccessoryDriver.async_start"
    ):
        await async_init_entry(hass, entry)

        homekit.status = STATUS_RUNNING
        acc_mock = MagicMock()
        acc_mock.entity_id = entity_id
        acc_mock.stop = AsyncMock()

        homekit.driver.accessory = acc_mock
        homekit.driver.aio_stop_event = MagicMock()

        await hass.services.async_call(
            DOMAIN,
            SERVICE_HOMEKIT_RESET_ACCESSORY,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert hk_driver_config_changed.call_count == 0
        homekit.status = STATUS_STOPPED


async def test_homekit_reset_single_accessory_no_match(
    hass: HomeAssistant, mock_async_zeroconf: None
) -> None:
    """Test resetting HomeKit single accessory when the entity id does not match."""

    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_NAME: "mock_name", CONF_PORT: 12345}
    )
    entity_id = "light.demo"
    homekit = _mock_homekit(hass, entry, HOMEKIT_MODE_ACCESSORY)

    with patch(f"{PATH_HOMEKIT}.HomeKit", return_value=homekit), patch(
        "pyhap.accessory_driver.AccessoryDriver.config_changed"
    ) as hk_driver_config_changed, patch(
        "pyhap.accessory_driver.AccessoryDriver.async_start"
    ):
        await async_init_entry(hass, entry)

        homekit.status = STATUS_RUNNING
        acc_mock = MagicMock()
        acc_mock.entity_id = entity_id
        acc_mock.stop = AsyncMock()

        homekit.driver.accessory = acc_mock
        homekit.driver.aio_stop_event = MagicMock()

        await hass.services.async_call(
            DOMAIN,
            SERVICE_HOMEKIT_RESET_ACCESSORY,
            {ATTR_ENTITY_ID: "light.no_match"},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert hk_driver_config_changed.call_count == 0
        homekit.status = STATUS_STOPPED


async def test_homekit_too_many_accessories(
    hass: HomeAssistant,
    hk_driver,
    caplog: pytest.LogCaptureFixture,
    mock_async_zeroconf: None,
) -> None:
    """Test adding too many accessories to HomeKit."""
    entry = await async_init_integration(hass)

    entity_filter = generate_filter(["cover", "light"], ["demo.test"], [], [])

    homekit = _mock_homekit(hass, entry, HOMEKIT_MODE_BRIDGE, entity_filter)

    def _mock_bridge(*_):
        mock_bridge = HomeBridge(hass, hk_driver, "mock_bridge")
        # The bridge itself counts as an accessory
        mock_bridge.accessories = range(MAX_DEVICES)
        return mock_bridge

    homekit.driver = hk_driver
    homekit.driver.accessory = Accessory(hk_driver, "any")

    hass.states.async_set("light.demo", "on")
    hass.states.async_set("light.demo2", "on")
    hass.states.async_set("light.demo3", "on")

    with patch("pyhap.accessory_driver.AccessoryDriver.async_start"), patch(
        f"{PATH_HOMEKIT}.async_show_setup_message"
    ), patch(f"{PATH_HOMEKIT}.HomeBridge", _mock_bridge):
        await homekit.async_start()
        await hass.async_block_till_done()
        assert "would exceed" in caplog.text


async def test_homekit_finds_linked_batteries(
    hass: HomeAssistant,
    hk_driver,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_async_zeroconf: None,
) -> None:
    """Test HomeKit start method."""
    entry = await async_init_integration(hass)

    homekit = _mock_homekit(hass, entry, HOMEKIT_MODE_BRIDGE)

    homekit.driver = hk_driver
    homekit.bridge = MagicMock()

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        sw_version="0.16.0",
        hw_version="2.34",
        model="Powerwall 2",
        manufacturer="Tesla",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    binary_charging_sensor = entity_registry.async_get_or_create(
        "binary_sensor",
        "powerwall",
        "battery_charging",
        device_id=device_entry.id,
        original_device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    )
    battery_sensor = entity_registry.async_get_or_create(
        "sensor",
        "powerwall",
        "battery",
        device_id=device_entry.id,
        original_device_class=SensorDeviceClass.BATTERY,
    )
    light = entity_registry.async_get_or_create(
        "light", "powerwall", "demo", device_id=device_entry.id
    )

    hass.states.async_set(
        binary_charging_sensor.entity_id,
        STATE_ON,
        {ATTR_DEVICE_CLASS: BinarySensorDeviceClass.BATTERY_CHARGING},
    )
    hass.states.async_set(
        battery_sensor.entity_id, 30, {ATTR_DEVICE_CLASS: SensorDeviceClass.BATTERY}
    )
    hass.states.async_set(light.entity_id, STATE_ON)

    with patch(f"{PATH_HOMEKIT}.async_show_setup_message"), patch(
        f"{PATH_HOMEKIT}.get_accessory"
    ) as mock_get_acc, patch("pyhap.accessory_driver.AccessoryDriver.async_start"):
        await homekit.async_start()
    await hass.async_block_till_done()

    mock_get_acc.assert_called_with(
        hass,
        ANY,
        ANY,
        ANY,
        {
            "manufacturer": "Tesla",
            "model": "Powerwall 2",
            "sw_version": "0.16.0",
            "hw_version": "2.34",
            "platform": "test",
            "linked_battery_charging_sensor": "binary_sensor.powerwall_battery_charging",
            "linked_battery_sensor": "sensor.powerwall_battery",
        },
    )


async def test_homekit_async_get_integration_fails(
    hass: HomeAssistant,
    hk_driver,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_async_zeroconf: None,
) -> None:
    """Test that we continue if async_get_integration fails."""
    entry = await async_init_integration(hass)
    homekit = _mock_homekit(hass, entry, HOMEKIT_MODE_BRIDGE)

    homekit.driver = hk_driver
    homekit.bridge = HomeBridge(hass, hk_driver, "mock_bridge")

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        sw_version="0.16.0",
        model="Powerwall 2",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    binary_charging_sensor = entity_registry.async_get_or_create(
        "binary_sensor",
        "invalid_integration_does_not_exist",
        "battery_charging",
        device_id=device_entry.id,
        original_device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    )
    battery_sensor = entity_registry.async_get_or_create(
        "sensor",
        "invalid_integration_does_not_exist",
        "battery",
        device_id=device_entry.id,
        original_device_class=SensorDeviceClass.BATTERY,
    )
    light = entity_registry.async_get_or_create(
        "light", "invalid_integration_does_not_exist", "demo", device_id=device_entry.id
    )

    hass.states.async_set(
        binary_charging_sensor.entity_id,
        STATE_ON,
        {ATTR_DEVICE_CLASS: BinarySensorDeviceClass.BATTERY_CHARGING},
    )
    hass.states.async_set(
        battery_sensor.entity_id, 30, {ATTR_DEVICE_CLASS: SensorDeviceClass.BATTERY}
    )
    hass.states.async_set(light.entity_id, STATE_ON)

    with patch.object(homekit.bridge, "add_accessory"), patch(
        f"{PATH_HOMEKIT}.async_show_setup_message"
    ), patch(f"{PATH_HOMEKIT}.get_accessory") as mock_get_acc, patch(
        "pyhap.accessory_driver.AccessoryDriver.async_start"
    ):
        await homekit.async_start()
    await hass.async_block_till_done()

    mock_get_acc.assert_called_with(
        hass,
        ANY,
        ANY,
        ANY,
        {
            "model": "Powerwall 2",
            "sw_version": "0.16.0",
            "platform": "invalid_integration_does_not_exist",
            "linked_battery_charging_sensor": "binary_sensor.invalid_integration_does_not_exist_battery_charging",
            "linked_battery_sensor": "sensor.invalid_integration_does_not_exist_battery",
        },
    )


async def test_yaml_updates_update_config_entry_for_name(
    hass: HomeAssistant, mock_async_zeroconf: None
) -> None:
    """Test async_setup with imported config."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_IMPORT,
        data={CONF_NAME: BRIDGE_NAME, CONF_PORT: DEFAULT_PORT},
        options={},
    )
    entry.add_to_hass(hass)

    with patch(f"{PATH_HOMEKIT}.HomeKit") as mock_homekit, patch(
        "homeassistant.components.network.async_get_source_ip", return_value="1.2.3.4"
    ):
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
        [None],
        ANY,
        ANY,
        {},
        HOMEKIT_MODE_BRIDGE,
        ["1.2.3.4", "10.10.10.10"],
        entry.entry_id,
        entry.title,
        devices=[],
    )

    # Test auto start enabled
    mock_homekit.reset_mock()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    mock_homekit().async_start.assert_called()


async def test_yaml_can_link_with_default_name(
    hass: HomeAssistant, mock_async_zeroconf: None
) -> None:
    """Test async_setup with imported config linked by default name."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_IMPORT,
        data={},
        options={},
    )
    entry.add_to_hass(hass)

    with patch(f"{PATH_HOMEKIT}.HomeKit") as mock_homekit, patch(
        "homeassistant.components.network.async_get_source_ip", return_value="1.2.3.4"
    ):
        mock_homekit.return_value = homekit = Mock()
        type(homekit).async_start = AsyncMock()
        assert await async_setup_component(
            hass,
            "homekit",
            {"homekit": {"entity_config": {"camera.back_camera": {"stream_count": 3}}}},
        )
        await hass.async_block_till_done()

    mock_homekit.reset_mock()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    assert entry.options["entity_config"]["camera.back_camera"]["stream_count"] == 3


async def test_yaml_can_link_with_port(
    hass: HomeAssistant, mock_async_zeroconf: None
) -> None:
    """Test async_setup with imported config linked by port."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_IMPORT,
        data={"name": "random", "port": 12345},
        options={},
    )
    entry.add_to_hass(hass)
    entry2 = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_IMPORT,
        data={"name": "random", "port": 12346},
        options={},
    )
    entry2.add_to_hass(hass)
    entry3 = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_ZEROCONF,
        data={"name": "random", "port": 12347},
        options={},
    )
    entry3.add_to_hass(hass)
    with patch(f"{PATH_HOMEKIT}.HomeKit") as mock_homekit, patch(
        "homeassistant.components.network.async_get_source_ip", return_value="1.2.3.4"
    ):
        mock_homekit.return_value = homekit = Mock()
        type(homekit).async_start = AsyncMock()
        assert await async_setup_component(
            hass,
            "homekit",
            {
                "homekit": {
                    "port": 12345,
                    "entity_config": {"camera.back_camera": {"stream_count": 3}},
                }
            },
        )
        await hass.async_block_till_done()

    mock_homekit.reset_mock()
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    assert entry.options["entity_config"]["camera.back_camera"]["stream_count"] == 3
    assert entry2.options == {}
    assert entry3.options == {}


async def test_homekit_uses_system_zeroconf(
    hass: HomeAssistant, hk_driver, mock_async_zeroconf: None
) -> None:
    """Test HomeKit uses system zeroconf."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: BRIDGE_NAME, CONF_PORT: DEFAULT_PORT},
        options={},
    )
    assert await async_setup_component(hass, "zeroconf", {"zeroconf": {}})
    system_async_zc = await zeroconf.async_get_async_instance(hass)

    with patch("pyhap.accessory_driver.AccessoryDriver.async_start"), patch(
        f"{PATH_HOMEKIT}.HomeKit.async_stop"
    ), patch(f"{PATH_HOMEKIT}.async_port_is_available"):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert (
            hass.data[DOMAIN][entry.entry_id][HOMEKIT].driver.advertiser
            == system_async_zc
        )
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_homekit_ignored_missing_devices(
    hass: HomeAssistant,
    hk_driver,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_async_zeroconf: None,
) -> None:
    """Test HomeKit handles a device in the entity registry but missing from the device registry."""

    entry = await async_init_integration(hass)
    homekit = _mock_homekit(hass, entry, HOMEKIT_MODE_BRIDGE)

    homekit.driver = hk_driver
    homekit.bridge = _mock_pyhap_bridge()

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        sw_version="0.16.0",
        model="Powerwall 2",
        manufacturer="Tesla",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    entity_registry.async_get_or_create(
        "binary_sensor",
        "powerwall",
        "battery_charging",
        device_id=device_entry.id,
        original_device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    )
    entity_registry.async_get_or_create(
        "sensor",
        "powerwall",
        "battery",
        device_id=device_entry.id,
        original_device_class=SensorDeviceClass.BATTERY,
    )
    light = entity_registry.async_get_or_create(
        "light", "powerwall", "demo", device_id=device_entry.id
    )
    # Delete the device to make sure we fallback
    # to using the platform
    device_registry.async_remove_device(device_entry.id)
    # Wait for the entities to be removed
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    # Restore the registry
    entity_registry.async_get_or_create(
        "binary_sensor",
        "powerwall",
        "battery_charging",
        device_id=device_entry.id,
        original_device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    )
    entity_registry.async_get_or_create(
        "sensor",
        "powerwall",
        "battery",
        device_id=device_entry.id,
        original_device_class=SensorDeviceClass.BATTERY,
    )
    light = entity_registry.async_get_or_create(
        "light", "powerwall", "demo", device_id=device_entry.id
    )

    hass.states.async_set(light.entity_id, STATE_ON)
    hass.states.async_set("light.two", STATE_ON)

    with patch(f"{PATH_HOMEKIT}.get_accessory") as mock_get_acc, patch(
        f"{PATH_HOMEKIT}.HomeBridge", return_value=homekit.bridge
    ), patch("pyhap.accessory_driver.AccessoryDriver.async_start"):
        await homekit.async_start()
        await hass.async_block_till_done()

    mock_get_acc.assert_any_call(
        hass,
        ANY,
        ANY,
        ANY,
        {
            "platform": "Tesla Powerwall",
            "linked_battery_charging_sensor": "binary_sensor.powerwall_battery_charging",
            "linked_battery_sensor": "sensor.powerwall_battery",
        },
    )


async def test_homekit_finds_linked_motion_sensors(
    hass: HomeAssistant,
    hk_driver,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_async_zeroconf: None,
) -> None:
    """Test HomeKit start method."""
    entry = await async_init_integration(hass)

    homekit = _mock_homekit(hass, entry, HOMEKIT_MODE_BRIDGE)

    homekit.driver = hk_driver
    homekit.bridge = HomeBridge(hass, hk_driver, "mock_bridge")

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        sw_version="0.16.0",
        model="Camera Server",
        manufacturer="Ubq",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    binary_motion_sensor = entity_registry.async_get_or_create(
        "binary_sensor",
        "camera",
        "motion_sensor",
        device_id=device_entry.id,
        original_device_class=BinarySensorDeviceClass.MOTION,
    )
    camera = entity_registry.async_get_or_create(
        "camera", "camera", "demo", device_id=device_entry.id
    )

    hass.states.async_set(
        binary_motion_sensor.entity_id,
        STATE_ON,
        {ATTR_DEVICE_CLASS: BinarySensorDeviceClass.MOTION},
    )
    hass.states.async_set(camera.entity_id, STATE_ON)

    with patch.object(homekit.bridge, "add_accessory"), patch(
        f"{PATH_HOMEKIT}.async_show_setup_message"
    ), patch(f"{PATH_HOMEKIT}.get_accessory") as mock_get_acc, patch(
        "pyhap.accessory_driver.AccessoryDriver.async_start"
    ):
        await homekit.async_start()
    await hass.async_block_till_done()

    mock_get_acc.assert_called_with(
        hass,
        ANY,
        ANY,
        ANY,
        {
            "manufacturer": "Ubq",
            "model": "Camera Server",
            "platform": "test",
            "sw_version": "0.16.0",
            "linked_motion_sensor": "binary_sensor.camera_motion_sensor",
        },
    )


async def test_homekit_finds_linked_humidity_sensors(
    hass: HomeAssistant,
    hk_driver,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_async_zeroconf: None,
) -> None:
    """Test HomeKit start method."""
    entry = await async_init_integration(hass)

    homekit = _mock_homekit(hass, entry, HOMEKIT_MODE_BRIDGE)

    homekit.driver = hk_driver
    homekit.bridge = HomeBridge(hass, hk_driver, "mock_bridge")

    config_entry = MockConfigEntry(domain="test", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        sw_version="0.16.1",
        model="Smart Brainy Clever Humidifier",
        manufacturer="Home Assistant",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    humidity_sensor = entity_registry.async_get_or_create(
        "sensor",
        "humidifier",
        "humidity_sensor",
        device_id=device_entry.id,
        original_device_class=SensorDeviceClass.HUMIDITY,
    )
    humidifier = entity_registry.async_get_or_create(
        "humidifier", "humidifier", "demo", device_id=device_entry.id
    )

    hass.states.async_set(
        humidity_sensor.entity_id,
        "42",
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.HUMIDITY,
            ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
        },
    )
    hass.states.async_set(humidifier.entity_id, STATE_ON)

    with patch.object(homekit.bridge, "add_accessory"), patch(
        f"{PATH_HOMEKIT}.async_show_setup_message"
    ), patch(f"{PATH_HOMEKIT}.get_accessory") as mock_get_acc, patch(
        "pyhap.accessory_driver.AccessoryDriver.async_start"
    ):
        await homekit.async_start()
    await hass.async_block_till_done()

    mock_get_acc.assert_called_with(
        hass,
        ANY,
        ANY,
        ANY,
        {
            "manufacturer": "Home Assistant",
            "model": "Smart Brainy Clever Humidifier",
            "platform": "test",
            "sw_version": "0.16.1",
            "linked_humidity_sensor": "sensor.humidifier_humidity_sensor",
        },
    )


async def test_reload(hass: HomeAssistant, mock_async_zeroconf: None) -> None:
    """Test we can reload from yaml."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_IMPORT,
        data={CONF_NAME: "reloadable", CONF_PORT: 12345},
        options={},
    )
    entry.add_to_hass(hass)

    with patch(f"{PATH_HOMEKIT}.HomeKit") as mock_homekit, patch(
        "homeassistant.components.network.async_get_source_ip", return_value="1.2.3.4"
    ):
        mock_homekit.return_value = homekit = Mock()
        assert await async_setup_component(
            hass, "homekit", {"homekit": {CONF_NAME: "reloadable", CONF_PORT: 12345}}
        )
        await hass.async_block_till_done()

    mock_homekit.assert_any_call(
        hass,
        "reloadable",
        12345,
        [None],
        ANY,
        False,
        {},
        HOMEKIT_MODE_BRIDGE,
        ["1.2.3.4", "10.10.10.10"],
        entry.entry_id,
        entry.title,
        devices=[],
    )
    yaml_path = get_fixture_path("configuration.yaml", "homekit")
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path), patch(
        f"{PATH_HOMEKIT}.HomeKit"
    ) as mock_homekit2, patch.object(homekit.bridge, "add_accessory"), patch(
        f"{PATH_HOMEKIT}.async_show_setup_message"
    ), patch(
        f"{PATH_HOMEKIT}.get_accessory"
    ), patch(
        "pyhap.accessory_driver.AccessoryDriver.async_start"
    ), patch(
        "homeassistant.components.network.async_get_source_ip", return_value="1.2.3.4"
    ):
        mock_homekit2.return_value = homekit = Mock()
        await hass.services.async_call(
            "homekit",
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_homekit2.assert_any_call(
        hass,
        "reloadable",
        45678,
        [None],
        ANY,
        False,
        {},
        HOMEKIT_MODE_BRIDGE,
        ["1.2.3.4", "10.10.10.10"],
        entry.entry_id,
        entry.title,
        devices=[],
    )


async def test_homekit_start_in_accessory_mode(
    hass: HomeAssistant,
    hk_driver,
    mock_async_zeroconf: None,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test HomeKit start method in accessory mode."""
    entry = await async_init_integration(hass)

    homekit = _mock_homekit(hass, entry, HOMEKIT_MODE_ACCESSORY)

    homekit.bridge = Mock()
    homekit.bridge.accessories = []
    homekit.driver = hk_driver
    homekit.driver.accessory = Accessory(hk_driver, "any")

    hass.states.async_set("light.demo", "on")

    with patch(f"{PATH_HOMEKIT}.HomeKit.add_bridge_accessory") as mock_add_acc, patch(
        f"{PATH_HOMEKIT}.async_show_setup_message"
    ) as mock_setup_msg, patch(
        "pyhap.accessory_driver.AccessoryDriver.async_start"
    ) as hk_driver_start:
        await homekit.async_start()

    await hass.async_block_till_done()
    mock_add_acc.assert_not_called()
    mock_setup_msg.assert_called_with(
        hass, entry.entry_id, "Mock Title (demo)", ANY, ANY
    )
    assert hk_driver_start.called
    assert homekit.status == STATUS_RUNNING


async def test_homekit_start_in_accessory_mode_unsupported_entity(
    hass: HomeAssistant,
    hk_driver,
    mock_async_zeroconf: None,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test HomeKit start method in accessory mode with an unsupported entity."""
    entry = await async_init_integration(hass)

    homekit = _mock_homekit(hass, entry, HOMEKIT_MODE_ACCESSORY)

    homekit.bridge = Mock()
    homekit.bridge.accessories = []
    homekit.driver = hk_driver
    homekit.driver.accessory = Accessory(hk_driver, "any")

    hass.states.async_set("notsupported.demo", "on")

    with patch(f"{PATH_HOMEKIT}.HomeKit.add_bridge_accessory") as mock_add_acc, patch(
        f"{PATH_HOMEKIT}.async_show_setup_message"
    ) as mock_setup_msg, patch(
        "pyhap.accessory_driver.AccessoryDriver.async_start"
    ) as hk_driver_start:
        await homekit.async_start()

    await hass.async_block_till_done()
    assert not mock_add_acc.called
    assert not mock_setup_msg.called
    assert not hk_driver_start.called
    assert homekit.status == STATUS_WAIT
    assert "entity not supported" in caplog.text


async def test_homekit_start_in_accessory_mode_missing_entity(
    hass: HomeAssistant,
    hk_driver,
    mock_async_zeroconf: None,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test HomeKit start method in accessory mode when entity is not available."""
    entry = await async_init_integration(hass)

    homekit = _mock_homekit(hass, entry, HOMEKIT_MODE_ACCESSORY)

    homekit.bridge = Mock()
    homekit.bridge.accessories = []
    homekit.driver = hk_driver
    homekit.driver.accessory = Accessory(hk_driver, "any")

    with patch(f"{PATH_HOMEKIT}.HomeKit.add_bridge_accessory") as mock_add_acc, patch(
        f"{PATH_HOMEKIT}.async_show_setup_message"
    ), patch("pyhap.accessory_driver.AccessoryDriver.async_start"):
        await homekit.async_start()

    await hass.async_block_till_done()
    mock_add_acc.assert_not_called()
    assert homekit.status == STATUS_WAIT

    assert "entity not available" in caplog.text


async def test_wait_for_port_to_free(
    hass: HomeAssistant,
    hk_driver,
    mock_async_zeroconf: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test we wait for the port to free before declaring unload success."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: BRIDGE_NAME, CONF_PORT: DEFAULT_PORT},
        options={},
    )
    entry.add_to_hass(hass)

    with patch("pyhap.accessory_driver.AccessoryDriver.async_start"), patch(
        f"{PATH_HOMEKIT}.HomeKit.async_stop"
    ), patch(f"{PATH_HOMEKIT}.async_port_is_available", return_value=True) as port_mock:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert "Waiting for the HomeKit server to shutdown" not in caplog.text
        assert port_mock.called

    with patch("pyhap.accessory_driver.AccessoryDriver.async_start"), patch(
        f"{PATH_HOMEKIT}.HomeKit.async_stop"
    ), patch.object(homekit_base, "PORT_CLEANUP_CHECK_INTERVAL_SECS", 0), patch(
        f"{PATH_HOMEKIT}.async_port_is_available", return_value=False
    ) as port_mock:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert "Waiting for the HomeKit server to shutdown" in caplog.text
        assert port_mock.called
