"""Test options flow."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.yamaha_musiccast.const import (
    CONF_DISPLAYED_SOURCES,
    CONF_HIDDEN_SOURCES,
    DEFAULT_ZONE,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def _setup_entry(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_options_flow_defaults_to_all_sources_displayed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_musiccast_device,
) -> None:
    """Test the options flow defaults to showing every known source."""
    await _setup_entry(hass, mock_config_entry)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    (field,) = result["data_schema"].schema
    assert sorted(field.default()) == ["bluetooth", "net_radio"]


async def test_options_flow_hides_unselected_sources(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_musiccast_device,
) -> None:
    """Test unselecting a source stores it as hidden."""
    await _setup_entry(hass, mock_config_entry)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_DISPLAYED_SOURCES: ["net_radio"]},
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {CONF_HIDDEN_SOURCES: ["bluetooth"]}
    assert mock_config_entry.options == {CONF_HIDDEN_SOURCES: ["bluetooth"]}


async def test_options_flow_reflects_previously_hidden_sources(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_musiccast_device,
) -> None:
    """Test the options flow unchecks sources that are already hidden."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_HIDDEN_SOURCES: ["bluetooth"]}
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    (field,) = result["data_schema"].schema
    assert field.default() == ["net_radio"]


async def test_options_flow_ignores_sources_discovered_after_form_shown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_musiccast_device,
) -> None:
    """Test a source appearing after the form was shown isn't hidden."""
    await _setup_entry(hass, mock_config_entry)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    # Simulate the receiver reporting a new input before the form is submitted.
    main_zone = mock_musiccast_device.data.zones[DEFAULT_ZONE]
    main_zone.input_list = [*main_zone.input_list, "spotify"]

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_DISPLAYED_SOURCES: ["net_radio", "bluetooth"]},
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {CONF_HIDDEN_SOURCES: []}


async def test_options_flow_aborts_when_entry_not_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_musiccast_device,
) -> None:
    """Test the options flow aborts if the entry is not loaded."""
    await _setup_entry(hass, mock_config_entry)
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_loaded"
