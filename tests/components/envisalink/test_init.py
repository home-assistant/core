"""Test the Envisalink initialization."""

from unittest.mock import PropertyMock, patch

from pyenvisalink.alarm_panel import EnvisalinkAlarmPanel
from pyenvisalink.const import PANEL_TYPE_HONEYWELL
import pytest

from homeassistant.components.envisalink.const import (
    CONF_CREATE_ZONE_BYPASS_SWITCHES,
    CONF_HONEYWELL_ARM_NIGHT_MODE,
    DEFAULT_HONEYWELL_ARM_NIGHT_MODE,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_load_unload_config_entry(hass: HomeAssistant, init_integration) -> None:
    """Test loading and unloading the integration."""
    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries
    assert len(entries) == 1

    assert hass.data[DOMAIN]
    assert hass.data[DOMAIN][entries[0].entry_id]

    # Test a reload
    result = hass.config_entries.async_update_entry(init_integration, options={})
    await hass.async_block_till_done()
    assert result

    # Unload the integration
    await hass.config_entries.async_unload(entries[0].entry_id)
    await hass.async_block_till_done()

    # Ensure everything is cleaned up nicely and are disconnected
    assert not hass.data.get(DOMAIN)


async def test_async_setup_import(
    hass: HomeAssistant,
    mock_yaml_import_data,
    mock_envisalink_alarm_panel,
    mock_config_entry_yaml_import,
) -> None:
    """Test importing from configuration.yaml."""
    result = await async_setup_component(hass, DOMAIN, {DOMAIN: mock_yaml_import_data})
    assert result

    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries
    assert len(entries) == 1
    data = entries[0].data
    options = entries[0].options

    assert data == mock_config_entry_yaml_import.data
    assert options == mock_config_entry_yaml_import.options


async def test_async_setup_import_update(
    hass: HomeAssistant,
    mock_config_data_result,
    mock_unique_id,
    mock_yaml_import_data,
    mock_envisalink_alarm_panel,
    mock_config_entry_yaml_options,
) -> None:
    """Test importing from configuration.yaml with differences from the config entry."""

    mock_config_entry_yaml_options.add_to_hass(hass)

    result = await async_setup_component(hass, DOMAIN, {DOMAIN: mock_yaml_import_data})
    assert result

    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries
    assert len(entries) == 1

    # Confirm the zone bypass switches don't exit yet
    state = hass.states.get("switch.family_room_bypass")
    assert not state

    state = hass.states.get("switch.basement_bypass")
    assert not state

    # Unload the integration
    config_entry = entries[0]
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert not hass.data.get(DOMAIN)

    # Add the zone bypass switch option to the config entry
    config_entry.add_to_hass(hass)
    options = dict(config_entry.options)
    options[CONF_CREATE_ZONE_BYPASS_SWITCHES] = True
    assert hass.config_entries.async_update_entry(config_entry, options=options)

    # Reload it and make sure the zone bypass switches got created
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("switch.family_room_bypass")
    assert state
    assert state.state == STATE_OFF

    state = hass.states.get("switch.basement_bypass")
    assert state
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    "alarm_error",
    [
        EnvisalinkAlarmPanel.ConnectionResult.INVALID_AUTHORIZATION,
        EnvisalinkAlarmPanel.ConnectionResult.CONNECTION_FAILED,
        EnvisalinkAlarmPanel.ConnectionResult.INVALID_PANEL_TYPE,
        EnvisalinkAlarmPanel.ConnectionResult.INVALID_EVL_VERSION,
        EnvisalinkAlarmPanel.ConnectionResult.DISCOVERY_NOT_COMPLETE,
        "unknown",
    ],
)
async def test_init_fail(
    hass: HomeAssistant,
    mock_config_entry,
    mock_envisalink_alarm_panel,
    alarm_error,
) -> None:
    """Test startup failures."""
    with patch(
        "pyenvisalink.alarm_panel.EnvisalinkAlarmPanel.start",
        return_value=alarm_error,
    ):
        mock_config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_mismatched_mac(
    hass: HomeAssistant, mock_unique_id, mock_config_entry, mock_envisalink_alarm_panel
) -> None:
    """Test when the discovered MAC doesn't match the unique ID."""
    mock_config_entry.add_to_hass(hass)

    changed_mac = "1234567890"

    with patch.object(
        EnvisalinkAlarmPanel,
        "mac_address",
        new_callable=PropertyMock,
        return_value=changed_mac,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        controller = hass.data[DOMAIN][mock_config_entry.entry_id]
        controller.async_login_success_callback()
        await hass.async_block_till_done()

        assert mock_config_entry.unique_id == mock_unique_id
        assert mock_config_entry.unique_id != changed_mac


async def test_init_honeywell(
    hass: HomeAssistant, mock_config_entry_honeywell, mock_envisalink_alarm_panel
) -> None:
    """Test initializing the integration as a Honeywell panel."""
    with patch.object(
        EnvisalinkAlarmPanel,
        "panel_type",
        new_callable=PropertyMock,
        return_value=PANEL_TYPE_HONEYWELL,
    ):
        mock_config_entry_honeywell.add_to_hass(hass)

        await hass.config_entries.async_setup(mock_config_entry_honeywell.entry_id)
        await hass.async_block_till_done()

        controller = hass.data[DOMAIN][mock_config_entry_honeywell.entry_id]
        controller.async_login_success_callback()
        await hass.async_block_till_done()

        assert controller.available
        assert (
            mock_config_entry_honeywell.options.get(CONF_HONEYWELL_ARM_NIGHT_MODE)
            == DEFAULT_HONEYWELL_ARM_NIGHT_MODE
        )
