"""Tests for the TP-Link component."""
from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock, patch

from pyHS100 import SmartBulb, SmartDevice, SmartDeviceException, SmartPlug, smartstrip
from pyHS100.smartdevice import EmeterStatus
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import tplink
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.tplink.common import SmartDevices
from homeassistant.components.tplink.const import (
    CONF_DIMMER,
    CONF_DISCOVERY,
    CONF_LIGHT,
    CONF_SW_VERSION,
    CONF_SWITCH,
    UNAVAILABLE_RETRY_DELAY,
)
from homeassistant.components.tplink.sensor import ENERGY_SENSORS
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component
from homeassistant.util import dt, slugify

from tests.common import MockConfigEntry, async_fire_time_changed, mock_coro
from tests.components.tplink.consts import (
    SMARTPLUG_HS100_DATA,
    SMARTPLUG_HS110_DATA,
    SMARTSTRIP_KP303_DATA,
)


async def test_creating_entry_tries_discover(hass):
    """Test setting up does discovery."""
    with patch(
        "homeassistant.components.tplink.async_setup_entry",
        return_value=mock_coro(True),
    ) as mock_setup, patch(
        "homeassistant.components.tplink.common.Discover.discover",
        return_value={"host": 1234},
    ):
        result = await hass.config_entries.flow.async_init(
            tplink.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 1


async def test_configuring_tplink_causes_discovery(hass):
    """Test that specifying empty config does discovery."""
    with patch("homeassistant.components.tplink.common.Discover.discover") as discover:
        discover.return_value = {"host": 1234}
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    assert len(discover.mock_calls) == 1


@pytest.mark.parametrize(
    "name,cls,platform",
    [
        ("pyHS100.SmartPlug", SmartPlug, "switch"),
        ("pyHS100.SmartBulb", SmartBulb, "light"),
    ],
)
@pytest.mark.parametrize("count", [1, 2, 3])
async def test_configuring_device_types(hass, name, cls, platform, count):
    """Test that light or switch platform list is filled correctly."""
    with patch(
        "homeassistant.components.tplink.common.Discover.discover"
    ) as discover, patch(
        "homeassistant.components.tplink.common.SmartDevice._query_helper"
    ), patch(
        "homeassistant.components.tplink.light.async_setup_entry",
        return_value=True,
    ):
        discovery_data = {
            f"123.123.123.{c}": cls("123.123.123.123") for c in range(count)
        }
        discover.return_value = discovery_data
        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    assert len(discover.mock_calls) == 1
    assert len(hass.data[tplink.DOMAIN][platform]) == count


class UnknownSmartDevice(SmartDevice):
    """Dummy class for testing."""

    @property
    def has_emeter(self) -> bool:
        """Do nothing."""

    def turn_off(self) -> None:
        """Do nothing."""

    def turn_on(self) -> None:
        """Do nothing."""

    @property
    def is_on(self) -> bool:
        """Do nothing."""

    @property
    def state_information(self) -> dict[str, Any]:
        """Do nothing."""


async def test_configuring_devices_from_multiple_sources(hass):
    """Test static and discover devices are not duplicated."""
    with patch(
        "homeassistant.components.tplink.common.Discover.discover"
    ) as discover, patch(
        "homeassistant.components.tplink.common.SmartDevice._query_helper"
    ), patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setup"
    ):
        discover_device_fail = SmartPlug("123.123.123.123")
        discover_device_fail.get_sysinfo = MagicMock(side_effect=SmartDeviceException())

        discover.return_value = {
            "123.123.123.1": SmartBulb("123.123.123.1"),
            "123.123.123.2": SmartPlug("123.123.123.2"),
            "123.123.123.3": SmartBulb("123.123.123.3"),
            "123.123.123.4": SmartPlug("123.123.123.4"),
            "123.123.123.123": discover_device_fail,
            "123.123.123.124": UnknownSmartDevice("123.123.123.124"),
        }

        await async_setup_component(
            hass,
            tplink.DOMAIN,
            {
                tplink.DOMAIN: {
                    CONF_LIGHT: [{CONF_HOST: "123.123.123.1"}],
                    CONF_SWITCH: [{CONF_HOST: "123.123.123.2"}],
                    CONF_DIMMER: [{CONF_HOST: "123.123.123.22"}],
                }
            },
        )
        await hass.async_block_till_done()

        assert len(discover.mock_calls) == 1
        assert len(hass.data[tplink.DOMAIN][CONF_LIGHT]) == 3
        assert len(hass.data[tplink.DOMAIN][CONF_SWITCH]) == 2


async def test_is_dimmable(hass):
    """Test that is_dimmable switches are correctly added as lights."""
    with patch(
        "homeassistant.components.tplink.common.Discover.discover"
    ) as discover, patch(
        "homeassistant.components.tplink.light.async_setup_entry",
        return_value=mock_coro(True),
    ) as setup, patch(
        "homeassistant.components.tplink.common.SmartDevice._query_helper"
    ), patch(
        "homeassistant.components.tplink.common.SmartPlug.is_dimmable", True
    ):
        dimmable_switch = SmartPlug("123.123.123.123")
        discover.return_value = {"host": dimmable_switch}

        await async_setup_component(hass, tplink.DOMAIN, {tplink.DOMAIN: {}})
        await hass.async_block_till_done()

    assert len(discover.mock_calls) == 1
    assert len(setup.mock_calls) == 1
    assert len(hass.data[tplink.DOMAIN][CONF_LIGHT]) == 1
    assert not hass.data[tplink.DOMAIN][CONF_SWITCH]


async def test_configuring_discovery_disabled(hass):
    """Test that discover does not get called when disabled."""
    with patch(
        "homeassistant.components.tplink.async_setup_entry",
        return_value=mock_coro(True),
    ) as mock_setup, patch(
        "homeassistant.components.tplink.common.Discover.discover", return_value=[]
    ) as discover:
        await async_setup_component(
            hass, tplink.DOMAIN, {tplink.DOMAIN: {tplink.CONF_DISCOVERY: False}}
        )
        await hass.async_block_till_done()

    assert discover.call_count == 0
    assert mock_setup.call_count == 1


async def test_platforms_are_initialized(hass: HomeAssistant):
    """Test that platforms are initialized per configuration array."""
    config = {
        tplink.DOMAIN: {
            CONF_DISCOVERY: False,
            CONF_LIGHT: [{CONF_HOST: "123.123.123.123"}],
            CONF_SWITCH: [{CONF_HOST: "321.321.321.321"}],
        }
    }

    with patch("homeassistant.components.tplink.common.Discover.discover"), patch(
        "homeassistant.components.tplink.get_static_devices"
    ) as get_static_devices, patch(
        "homeassistant.components.tplink.common.SmartDevice._query_helper"
    ), patch(
        "homeassistant.components.tplink.light.async_setup_entry",
        return_value=mock_coro(True),
    ), patch(
        "homeassistant.components.tplink.common.SmartPlug.is_dimmable",
        False,
    ):

        light = SmartBulb("123.123.123.123")
        switch = SmartPlug("321.321.321.321")
        switch.get_sysinfo = MagicMock(return_value=SMARTPLUG_HS110_DATA["sysinfo"])
        switch.get_emeter_realtime = MagicMock(
            return_value=EmeterStatus(SMARTPLUG_HS110_DATA["realtime"])
        )
        switch.get_emeter_daily = MagicMock(
            return_value={int(time.strftime("%e")): 1.123}
        )
        get_static_devices.return_value = SmartDevices([light], [switch])

        # patching is_dimmable is necessray to avoid misdetection as light.
        await async_setup_component(hass, tplink.DOMAIN, config)
        await hass.async_block_till_done()

        state = hass.states.get(f"switch.{switch.alias}")
        assert state
        assert state.name == switch.alias

        for description in ENERGY_SENSORS:
            state = hass.states.get(
                f"sensor.{switch.alias}_{slugify(description.name)}"
            )
            assert state
            assert state.state is not None
            assert state.name == f"{switch.alias} {description.name}"

        device_registry = dr.async_get(hass)
        assert len(device_registry.devices) == 1
        device = next(iter(device_registry.devices.values()))
        assert device.name == switch.alias
        assert device.model == switch.model
        assert device.connections == {(dr.CONNECTION_NETWORK_MAC, switch.mac.lower())}
        assert device.sw_version == switch.sys_info[CONF_SW_VERSION]


async def test_smartplug_without_consumption_sensors(hass: HomeAssistant):
    """Test that platforms are initialized per configuration array."""
    config = {
        tplink.DOMAIN: {
            CONF_DISCOVERY: False,
            CONF_SWITCH: [{CONF_HOST: "321.321.321.321"}],
        }
    }

    with patch("homeassistant.components.tplink.common.Discover.discover"), patch(
        "homeassistant.components.tplink.get_static_devices"
    ) as get_static_devices, patch(
        "homeassistant.components.tplink.common.SmartDevice._query_helper"
    ), patch(
        "homeassistant.components.tplink.light.async_setup_entry",
        return_value=mock_coro(True),
    ), patch(
        "homeassistant.components.tplink.common.SmartPlug.is_dimmable", False
    ):

        switch = SmartPlug("321.321.321.321")
        switch.get_sysinfo = MagicMock(return_value=SMARTPLUG_HS100_DATA["sysinfo"])
        get_static_devices.return_value = SmartDevices([], [switch])

        await async_setup_component(hass, tplink.DOMAIN, config)
        await hass.async_block_till_done()

        entities = hass.states.async_entity_ids(SWITCH_DOMAIN)
        assert len(entities) == 1

        entities = hass.states.async_entity_ids(SENSOR_DOMAIN)
        assert len(entities) == 0


async def test_smartstrip_device(hass: HomeAssistant):
    """Test discover a SmartStrip devices."""
    config = {
        tplink.DOMAIN: {
            CONF_DISCOVERY: True,
        }
    }

    class SmartStrip(smartstrip.SmartStrip):
        """Moked SmartStrip class."""

        def get_sysinfo(self):
            return SMARTSTRIP_KP303_DATA["sysinfo"]

    with patch(
        "homeassistant.components.tplink.common.Discover.discover"
    ) as discover, patch(
        "homeassistant.components.tplink.common.SmartDevice._query_helper"
    ), patch(
        "homeassistant.components.tplink.common.SmartPlug.get_sysinfo",
        return_value=SMARTSTRIP_KP303_DATA["sysinfo"],
    ):

        strip = SmartStrip("123.123.123.123")
        discover.return_value = {"123.123.123.123": strip}

        assert await async_setup_component(hass, tplink.DOMAIN, config)
        await hass.async_block_till_done()

        entities = hass.states.async_entity_ids(SWITCH_DOMAIN)
        assert len(entities) == 3


async def test_no_config_creates_no_entry(hass):
    """Test for when there is no tplink in config."""
    with patch(
        "homeassistant.components.tplink.async_setup_entry",
        return_value=mock_coro(True),
    ) as mock_setup:
        await async_setup_component(hass, tplink.DOMAIN, {})
        await hass.async_block_till_done()

    assert mock_setup.call_count == 0


async def test_not_available_at_startup(hass: HomeAssistant):
    """Test when configured devices are not available."""
    config = {
        tplink.DOMAIN: {
            CONF_DISCOVERY: False,
            CONF_SWITCH: [{CONF_HOST: "321.321.321.321"}],
        }
    }

    with patch("homeassistant.components.tplink.common.Discover.discover"), patch(
        "homeassistant.components.tplink.get_static_devices"
    ) as get_static_devices, patch(
        "homeassistant.components.tplink.common.SmartDevice._query_helper"
    ), patch(
        "homeassistant.components.tplink.light.async_setup_entry",
        return_value=mock_coro(True),
    ), patch(
        "homeassistant.components.tplink.common.SmartPlug.is_dimmable", False
    ):

        switch = SmartPlug("321.321.321.321")
        switch.get_sysinfo = MagicMock(side_effect=SmartDeviceException())
        get_static_devices.return_value = SmartDevices([], [switch])

        # run setup while device unreachable
        await async_setup_component(hass, tplink.DOMAIN, config)
        await hass.async_block_till_done()

        entries = hass.config_entries.async_entries(tplink.DOMAIN)
        assert len(entries) == 1
        assert entries[0].state is config_entries.ConfigEntryState.LOADED

        entities = hass.states.async_entity_ids(SWITCH_DOMAIN)
        assert len(entities) == 0

        # retrying with still unreachable device
        async_fire_time_changed(hass, dt.utcnow() + UNAVAILABLE_RETRY_DELAY)
        await hass.async_block_till_done()

        entries = hass.config_entries.async_entries(tplink.DOMAIN)
        assert len(entries) == 1
        assert entries[0].state is config_entries.ConfigEntryState.LOADED

        entities = hass.states.async_entity_ids(SWITCH_DOMAIN)
        assert len(entities) == 0

        # retrying with now reachable device
        switch.get_sysinfo = MagicMock(return_value=SMARTPLUG_HS100_DATA["sysinfo"])
        async_fire_time_changed(hass, dt.utcnow() + UNAVAILABLE_RETRY_DELAY)
        await hass.async_block_till_done()

        entries = hass.config_entries.async_entries(tplink.DOMAIN)
        assert len(entries) == 1
        assert entries[0].state is config_entries.ConfigEntryState.LOADED

        entities = hass.states.async_entity_ids(SWITCH_DOMAIN)
        assert len(entities) == 1


@pytest.mark.parametrize("platform", ["switch", "light"])
async def test_unload(hass, platform):
    """Test that the async_unload_entry works."""
    # As we have currently no configuration, we just to pass the domain here.
    entry = MockConfigEntry(domain=tplink.DOMAIN)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.tplink.get_static_devices"
    ) as get_static_devices, patch(
        "homeassistant.components.tplink.common.SmartDevice._query_helper"
    ), patch(
        f"homeassistant.components.tplink.{platform}.async_setup_entry",
        return_value=mock_coro(True),
    ) as async_setup_entry:
        config = {
            tplink.DOMAIN: {
                platform: [{CONF_HOST: "123.123.123.123"}],
                CONF_DISCOVERY: False,
            }
        }

        light = SmartBulb("123.123.123.123")
        switch = SmartPlug("321.321.321.321")
        switch.get_sysinfo = MagicMock(return_value=SMARTPLUG_HS110_DATA["sysinfo"])
        switch.get_emeter_realtime = MagicMock(
            return_value=EmeterStatus(SMARTPLUG_HS110_DATA["realtime"])
        )
        if platform == "light":
            get_static_devices.return_value = SmartDevices([light], [])
        elif platform == "switch":
            get_static_devices.return_value = SmartDevices([], [switch])

        assert await async_setup_component(hass, tplink.DOMAIN, config)
        await hass.async_block_till_done()

        assert len(async_setup_entry.mock_calls) == 1
        assert tplink.DOMAIN in hass.data

    assert await tplink.async_unload_entry(hass, entry)
    assert not hass.data[tplink.DOMAIN]
