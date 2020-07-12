"""Test the Bright Sky config flow."""
from homeassistant import config_entries, setup
from homeassistant.components.brightsky.const import DOMAIN

from tests.async_mock import patch


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.brightsky.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.brightsky.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "latitude": 50.102656,
                "longitude": 8.747893,
                "mode": "hourly",
                "name": "bright_sky",
            },
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "bright_sky"
    assert result2["data"] == {
        "latitude": 50.102656,
        "longitude": 8.747893,
        "mode": "hourly",
        "name": "bright_sky",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
