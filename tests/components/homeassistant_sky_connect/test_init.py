"""Test the Home Assistant Sky Connect integration."""
from unittest.mock import patch

import pytest

from homeassistant.components.homeassistant_sky_connect.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

CONFIG_ENTRY_DATA = {
    "device": "bla_device",
    "vid": "bla_vid",
    "pid": "bla_pid",
    "serial_number": "bla_serial_number",
    "manufacturer": "bla_manufacturer",
    "description": "bla_description",
}


@pytest.mark.parametrize(
    "onboarded, num_entries, num_flows", ((False, 1, 0), (True, 0, 1))
)
async def test_setup_entry(
    hass: HomeAssistant, onboarded, num_entries, num_flows
) -> None:
    """Test setup of a config entry, including setup of zha."""
    # Setup the config entry
    config_entry = MockConfigEntry(
        data=CONFIG_ENTRY_DATA,
        domain=DOMAIN,
        options={},
        title="Home Assistant Sky Connect",
    )
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.homeassistant_sky_connect.usb.async_is_plugged_in",
        return_value=True,
    ) as mock_is_plugged_in, patch(
        "homeassistant.components.onboarding.async_is_onboarded", return_value=onboarded
    ), patch(
        "zigpy_znp.zigbee.application.ControllerApplication.probe", return_value=True
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert len(mock_is_plugged_in.mock_calls) == 1

    assert len(hass.config_entries.async_entries("zha")) == num_entries
    assert len(hass.config_entries.flow.async_progress_by_handler("zha")) == num_flows


async def test_setup_zha(hass: HomeAssistant) -> None:
    """Test zha gets the right config."""
    # Setup the config entry
    config_entry = MockConfigEntry(
        data=CONFIG_ENTRY_DATA,
        domain=DOMAIN,
        options={},
        title="Home Assistant Sky Connect",
    )
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.homeassistant_sky_connect.usb.async_is_plugged_in",
        return_value=True,
    ) as mock_is_plugged_in, patch(
        "homeassistant.components.onboarding.async_is_onboarded", return_value=False
    ), patch(
        "zigpy_znp.zigbee.application.ControllerApplication.probe", return_value=True
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert len(mock_is_plugged_in.mock_calls) == 1

    config_entry = hass.config_entries.async_entries("zha")[0]
    assert config_entry.data == {
        "device": {"baudrate": 115200, "flow_control": None, "path": "bla_device"},
        "radio_type": "znp",
    }
    assert config_entry.options == {}
    assert config_entry.title == "bla_description"


async def test_setup_entry_wait_usb(hass: HomeAssistant) -> None:
    """Test setup of a config entry when the dongle is not plugged in."""
    # Setup the config entry
    config_entry = MockConfigEntry(
        data=CONFIG_ENTRY_DATA,
        domain=DOMAIN,
        options={},
        title="Home Assistant Sky Connect",
    )
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.homeassistant_sky_connect.usb.async_is_plugged_in",
        return_value=False,
    ) as mock_is_plugged_in:
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert len(mock_is_plugged_in.mock_calls) == 1
        assert config_entry.state == ConfigEntryState.SETUP_RETRY
