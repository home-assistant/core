"""Test the CO2 Signal config flow."""
from unittest.mock import patch

from homeassistant import config_entries, setup
from homeassistant.components.co2signal.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM


async def test_form_ok(hass: HomeAssistant) -> None:
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.co2signal.config_flow.CO2Signal.get_latest",
        return_value={"status": "ok"},
    ), patch(
        "homeassistant.components.co2signal.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "Test",
                "latitude": 12.3,
                "longitude": 45.6,
                "api_key": "api_key",
            },
        )
        await hass.async_block_till_done()

    print(result2)
    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Test"
    assert result2["data"] == {
        "name": "Test",
        "latitude": 12.3,
        "longitude": 45.6,
        "api_key": "api_key",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.co2signal.config_flow.CO2Signal.get_latest",
        side_effect=ValueError("Invalid authentication credentials"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "Test",
                "latitude": 12.3,
                "longitude": 45.6,
                "api_key": "api_key",
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "invalid_auth"}
