"""Define tests for the NextDNS config flow."""
from unittest.mock import patch

from homeassistant import data_entry_flow
from homeassistant.components.nextdns.const import CONF_PROFILE_NAME, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY

PROFILES = [{"id": "xyz12", "fingerprint": "aabbccdd123", "name": "Fake Profile"}]


async def test_form_create_entry(hass):
    """Test that the user step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == SOURCE_USER
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.nextdns.NextDns.get_profiles", return_value=PROFILES
    ), patch(
        "homeassistant.components.nextdns.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: "fake_api_key"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "profiles"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PROFILE_NAME: "Fake Profile"}
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Fake Profile"
    assert result["data"]["api_key"] == "fake_api_key"
    assert result["data"]["profile_id"] == "xyz12"
    assert len(mock_setup_entry.mock_calls) == 1
