"""Imports for test_config_flow.py."""

from homeassistant.components.uhooair.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import MOCK_CONFIG

from tests.common import MockConfigEntry


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER


async def test_invalid_credentials(hass: HomeAssistant, error_on_login) -> None:
    """Test that errors are shown when credentials are invalid."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=MOCK_CONFIG
    )

    assert result["errors"] == {"base": "auth"}


async def test_second_instance_error(
    hass: HomeAssistant,
    bypass_login,
    bypass_get_latest_data,
    bypass_get_devices,
    bypass_setup_devices,
) -> None:
    """Test that errors are shown when a second instance is added."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="1",
        data=MOCK_CONFIG,
    )
    config_entry.add_to_hass(hass)

    # Set up the first entry
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify the first entry is set up
    assert config_entry.state is ConfigEntryState.LOADED
    assert DOMAIN in hass.data
    assert config_entry.entry_id in hass.data[DOMAIN]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=MOCK_CONFIG
    )

    assert result["type"] == "abort"
    assert result["reason"] == "single_instance_allowed"

    # Clean up
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_create_entry(
    hass: HomeAssistant,
    bypass_async_setup_entry,
    bypass_login,
    bypass_get_latest_data,
    bypass_get_devices,
    bypass_setup_devices,
) -> None:
    """Test that the user step works."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=MOCK_CONFIG
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_API_KEY] == MOCK_CONFIG[CONF_API_KEY]
