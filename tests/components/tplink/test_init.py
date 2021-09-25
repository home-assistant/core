"""Tests for the TP-Link component."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from kasa import SmartBulb, SmartDevice, SmartPlug
from kasa.emeterstatus import EmeterStatus
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import tplink
from homeassistant.components.tplink.common import SmartDevices
from homeassistant.components.tplink.const import CONF_DISCOVERY
from homeassistant.const import CONF_HOST
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, mock_coro
from tests.components.tplink.consts import SMARTPLUG_HS110_DATA


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


async def test_no_config_creates_no_entry(hass):
    """Test for when there is no tplink in config."""
    with patch(
        "homeassistant.components.tplink.async_setup_entry",
        return_value=mock_coro(True),
    ) as mock_setup:
        await async_setup_component(hass, tplink.DOMAIN, {})
        await hass.async_block_till_done()

    assert mock_setup.call_count == 0


@pytest.mark.parametrize("platform", ["switch", "light"])
async def test_unload(hass, platform):
    """Test that the async_unload_entry works."""
    # As we have currently no configuration, we just to pass the domain here.
    entry = MockConfigEntry(domain=tplink.DOMAIN)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.tplink.get_static_devices"
    ) as get_static_devices, patch("kasa.smartdevice.SmartDevice._query_helper"), patch(
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
