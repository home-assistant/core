"""Test the Flipr config flow."""
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.flipr.const import (
    CONF_FLIPR_ID,
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
)


async def test_show_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == config_entries.SOURCE_USER


async def test_valid_credentials(hass):
    """Test valid login form."""
    with patch(
        "flipr_api.FliprAPIRestClient.search_flipr_ids",
        return_value=["flipid"],
    ) as mock_flipr_client, patch(
        "homeassistant.components.flipr.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.flipr.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.flipr.config_flow.encrypt_data",
        return_value="ENCRYPTED_DATA_ah_ah",
    ) as mock_crypt_util:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_USERNAME: "dummylogin",
                CONF_PASSWORD: "dummypass",
                CONF_FLIPR_ID: "flipid",
            },
        )
        await hass.async_block_till_done()

    assert len(mock_flipr_client.mock_calls) == 1
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_crypt_util.mock_calls) == 1

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Flipr device - flipid"
    assert result["data"] == {
        CONF_USERNAME: "dummylogin",
        CONF_PASSWORD: "ENCRYPTED_DATA_ah_ah",
        CONF_FLIPR_ID: "flipid",
    }
