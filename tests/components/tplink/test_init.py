"""Tests for the TP-Link component."""
from typing import Any, Dict
from unittest.mock import MagicMock, patch

from pyHS100 import SmartBulb, SmartDevice, SmartDeviceException, SmartPlug
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import tplink
from homeassistant.components.tplink.common import (
    CONF_DIMMER,
    CONF_DISCOVERY,
    CONF_LIGHT,
    CONF_SWITCH,
)
from homeassistant.const import CONF_HOST
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, mock_coro


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
        "homeassistant.components.tplink.light.async_setup_entry", return_value=True,
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
        pass

    def turn_off(self) -> None:
        """Do nothing."""
        pass

    def turn_on(self) -> None:
        """Do nothing."""
        pass

    @property
    def is_on(self) -> bool:
        """Do nothing."""
        pass

    @property
    def state_information(self) -> Dict[str, Any]:
        """Do nothing."""
        pass


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


async def test_platforms_are_initialized(hass):
    """Test that platforms are initialized per configuration array."""
    config = {
        tplink.DOMAIN: {
            CONF_DISCOVERY: False,
            CONF_LIGHT: [{CONF_HOST: "123.123.123.123"}],
            CONF_SWITCH: [{CONF_HOST: "321.321.321.321"}],
        }
    }

    with patch(
        "homeassistant.components.tplink.common.Discover.discover"
    ) as discover, patch(
        "homeassistant.components.tplink.common.SmartDevice._query_helper"
    ), patch(
        "homeassistant.components.tplink.light.async_setup_entry",
        return_value=mock_coro(True),
    ) as light_setup, patch(
        "homeassistant.components.tplink.switch.async_setup_entry",
        return_value=mock_coro(True),
    ) as switch_setup, patch(
        "homeassistant.components.tplink.common.SmartPlug.is_dimmable", False
    ):
        # patching is_dimmable is necessray to avoid misdetection as light.
        await async_setup_component(hass, tplink.DOMAIN, config)
        await hass.async_block_till_done()

    assert discover.call_count == 0
    assert light_setup.call_count == 1
    assert switch_setup.call_count == 1


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
        "homeassistant.components.tplink.common.SmartDevice._query_helper"
    ), patch(
        f"homeassistant.components.tplink.{platform}.async_setup_entry",
        return_value=mock_coro(True),
    ) as light_setup:
        config = {
            tplink.DOMAIN: {
                platform: [{CONF_HOST: "123.123.123.123"}],
                CONF_DISCOVERY: False,
            }
        }
        assert await async_setup_component(hass, tplink.DOMAIN, config)
        await hass.async_block_till_done()

        assert len(light_setup.mock_calls) == 1
        assert tplink.DOMAIN in hass.data

    assert await tplink.async_unload_entry(hass, entry)
    assert not hass.data[tplink.DOMAIN]
