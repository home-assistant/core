"""Test the Home Assistant Sky Connect integration."""
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components import zha
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


@pytest.fixture
def mock_zha_config_flow_setup() -> Generator[None, None, None]:
    """Mock the radio connection and probing of the ZHA config flow."""

    def mock_probe(config: dict[str, Any]) -> None:
        # The radio probing will return the correct baudrate
        return {**config, "baudrate": 115200}

    mock_connect_app = MagicMock()
    mock_connect_app.__aenter__.return_value.backups.backups = []

    with patch(
        "bellows.zigbee.application.ControllerApplication.probe", side_effect=mock_probe
    ), patch(
        "homeassistant.components.zha.config_flow.BaseZhaFlow._connect_zigpy_app",
        return_value=mock_connect_app,
    ):
        yield


@pytest.mark.parametrize(
    "onboarded, num_entries, num_flows", ((False, 1, 0), (True, 0, 1))
)
async def test_setup_entry(
    mock_zha_config_flow_setup, hass: HomeAssistant, onboarded, num_entries, num_flows
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
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert len(mock_is_plugged_in.mock_calls) == 1

    # Finish setting up ZHA
    if num_entries > 0:
        zha_flows = hass.config_entries.flow.async_progress_by_handler("zha")
        assert len(zha_flows) == 1
        assert zha_flows[0]["step_id"] == "choose_formation_strategy"

        await hass.config_entries.flow.async_configure(
            zha_flows[0]["flow_id"],
            user_input={"next_step_id": zha.config_flow.FORMATION_REUSE_SETTINGS},
        )
        await hass.async_block_till_done()

    assert len(hass.config_entries.flow.async_progress_by_handler("zha")) == num_flows
    assert len(hass.config_entries.async_entries("zha")) == num_entries


async def test_setup_zha(mock_zha_config_flow_setup, hass: HomeAssistant) -> None:
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
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert len(mock_is_plugged_in.mock_calls) == 1

    zha_flows = hass.config_entries.flow.async_progress_by_handler("zha")
    assert len(zha_flows) == 1
    assert zha_flows[0]["step_id"] == "choose_formation_strategy"

    # Finish setting up ZHA
    await hass.config_entries.flow.async_configure(
        zha_flows[0]["flow_id"],
        user_input={"next_step_id": zha.config_flow.FORMATION_REUSE_SETTINGS},
    )
    await hass.async_block_till_done()

    config_entry = hass.config_entries.async_entries("zha")[0]
    assert config_entry.data == {
        "device": {
            "baudrate": 115200,
            "flow_control": "software",
            "path": "bla_device",
        },
        "radio_type": "ezsp",
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
