"""Test the Aussie Broadband config flow."""
from unittest.mock import patch

from aussiebb import AuthenticationException

from homeassistant import config_entries
from homeassistant.components.aussie_broadband.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM


@patch("aussiebb.AussieBB")
async def test_form(aussie_bb, hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    aussie_bb_instance = aussie_bb.return_value
    aussie_bb_instance.get_services.return_value = [
        {"service_id": "12345678", "description": "Fake ABB Service"}
    ]

    with patch(
        "homeassistant.components.aussie_broadband.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Fake ABB Service"
    assert result2["data"] == {
        "service_id": "12345678",
        "username": "test-username",
        "password": "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@patch("aussiebb.AussieBB")
async def test_form_multiple_services(aussie_bb, hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    aussie_bb_instance = aussie_bb.return_value
    aussie_bb_instance.get_services.return_value = [
        {"service_id": "12345678", "description": "Fake ABB Service 1"},
        {"service_id": "87654321", "description": "Fake ABB Service 2"},
    ]

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "username": "test-username",
            "password": "test-password",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["step_id"] == "service"
    assert result2["errors"] is None

    with patch(
        "homeassistant.components.aussie_broadband.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"service_id": "87654321"},
        )
        await hass.async_block_till_done()

    assert result3["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result3["title"] == "Fake ABB Service 2"
    assert result3["data"] == {
        "service_id": "87654321",
        "username": "test-username",
        "password": "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@patch("aussiebb.AussieBB", side_effect=AuthenticationException())
async def test_form_invalid_auth(aussie_bb, hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "username": "test-username",
            "password": "test-password",
        },
    )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "invalid_credentials"}
