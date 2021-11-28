"""Test the RKI Covid numbers integration config flow."""
from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.rki_covid.const import DOMAIN
from homeassistant.core import HomeAssistant


async def test_successful_config_flow(hass: HomeAssistant) -> None:
    """Test a successful config flow with mock data."""
    # Initialize a config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Check that the config flow shows the user form
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    # Enter data into the config flow
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"county": "SK Amberg"},
    )

    # Validate the result
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "SK Amberg"
    assert result["result"]


async def test_successful_form(hass: HomeAssistant) -> None:
    """Test a successful form with mock data."""
    # Setup persistent notifications (will be skipped through a fixture)
    await setup.async_setup_component(hass, "persistent_notification", {})

    # Initialize a config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Check that the config flow
    assert result["type"] == "form"
    assert result["errors"] == {}

    # Enter data into the config flow
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"county": "LK München"},
    )

    # Validate the result
    assert result2["type"] == "create_entry"
    assert result2["title"] == "LK München"
    assert result2["data"] == {"county": "LK München"}
    await hass.async_block_till_done()
