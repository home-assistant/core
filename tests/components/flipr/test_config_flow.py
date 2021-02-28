"""Test the Flipr config flow."""
from unittest.mock import patch

import pytest
from requests.exceptions import HTTPError

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.flipr.const import (
    CONF_FLIPR_ID,
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
)


@pytest.fixture(name="mock_setup")
def mock_setups():
    """Prevent setup."""
    with patch("homeassistant.components.flipr.async_setup", return_value=True,), patch(
        "homeassistant.components.flipr.async_setup_entry",
        return_value=True,
    ):
        yield


async def test_show_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == config_entries.SOURCE_USER


async def test_invalid_credential(hass, mock_setup):
    """Test invalid credential."""
    with patch(
        "flipr_api.FliprAPIRestClient.search_flipr_ids", side_effect=HTTPError()
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_USERNAME: "bad_login",
                CONF_PASSWORD: "bad_pass",
                CONF_FLIPR_ID: "",
            },
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_nominal_case(hass, mock_setup):
    """Test valid login form."""
    with patch(
        "flipr_api.FliprAPIRestClient.search_flipr_ids",
        return_value=["flipid"],
    ) as mock_flipr_client, patch(
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
    assert len(mock_crypt_util.mock_calls) == 1

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Flipr device - flipid"
    assert result["result"].unique_id == "FLIPR_with_ID_" + "flipid"
    assert result["data"] == {
        CONF_USERNAME: "dummylogin",
        CONF_PASSWORD: "ENCRYPTED_DATA_ah_ah",
        CONF_FLIPR_ID: "flipid",
    }


async def test_multiple_flip_id(hass, mock_setup):
    """Test multiple flipr id adding a config step."""
    with patch(
        "flipr_api.FliprAPIRestClient.search_flipr_ids",
        return_value=["FLIP1", "FLIP2"],
    ) as mock_flipr_client, patch(
        "homeassistant.components.flipr.config_flow.encrypt_data",
        return_value="ENCRYPTED_DATA_ah_ah",
    ) as mock_crypt_util:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_USERNAME: "dummylogin",
                CONF_PASSWORD: "dummypass",
            },
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "flipr_id"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_FLIPR_ID: "FLIP2"},
        )

    assert len(mock_flipr_client.mock_calls) == 1
    assert len(mock_crypt_util.mock_calls) == 1

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Flipr device - FLIP2"
    assert result["result"].unique_id == "FLIPR_with_ID_" + "FLIP2"
    assert result["data"] == {
        CONF_USERNAME: "dummylogin",
        CONF_PASSWORD: "ENCRYPTED_DATA_ah_ah",
        CONF_FLIPR_ID: "FLIP2",
    }


async def test_no_flip_id(hass, mock_setup):
    """Test no flipr id entered."""
    with patch(
        "flipr_api.FliprAPIRestClient.search_flipr_ids",
        return_value=[],
    ) as mock_flipr_client, patch(
        "homeassistant.components.flipr.config_flow.encrypt_data",
        return_value="ENCRYPTED_DATA_ah_ah",
    ) as mock_crypt_util:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_USERNAME: "dummylogin",
                CONF_PASSWORD: "dummypass",
            },
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "flipr_id"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_FLIPR_ID: "FLIP_Entered"},
        )

    assert len(mock_flipr_client.mock_calls) == 1
    assert len(mock_crypt_util.mock_calls) == 1

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Flipr device - FLIP_Entered"
    assert result["result"].unique_id == "FLIPR_with_ID_" + "FLIP_Entered"
    assert result["data"] == {
        CONF_USERNAME: "dummylogin",
        CONF_PASSWORD: "ENCRYPTED_DATA_ah_ah",
        CONF_FLIPR_ID: "FLIP_Entered",
    }
