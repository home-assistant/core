"""Test the Envisalink config flow."""

# from homeassistant.components.envisalink import async_setup
from homeassistant.components.envisalink.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_load_unload_config_entry(hass: HomeAssistant, init_integration) -> None:
    """Test loading and unloading the integration."""
    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries
    assert len(entries) == 1

    assert hass.data[DOMAIN]
    assert hass.data[DOMAIN][entries[0].entry_id]
    # TODO

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
    assert options == {}


async def test_async_setup_import_update(
    hass: HomeAssistant,
    mock_config_data_result,
    mock_unique_id,
    mock_yaml_import_data,
    mock_envisalink_alarm_panel,
    mock_config_entry_yaml_options,
) -> None:
    """Test importing from configuration.yaml."""

    mock_config_entry_yaml_options.add_to_hass(hass)

    result = await async_setup_component(hass, DOMAIN, {DOMAIN: mock_yaml_import_data})
    assert result

    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries
    assert len(entries) == 1
    entries[0].data
    entries[0].options


#    assert options == {}
# TODO
