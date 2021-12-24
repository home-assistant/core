"""Test the Hyundai / Kia Connect config flow."""
from unittest.mock import patch

from hyundai_kia_connect_api import Token

from homeassistant import config_entries
from homeassistant.components.hyundai_kia_connect.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "hyundai_kia_connect_api.KiaUvoApiEU.login",
        return_value=Token(
            {"vehicle_name": "kia niro", "key": "value", "vehicle_id": "123456789"}
        ),
    ), patch(
        "homeassistant.components.hyundai_kia_connect.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "region": 1,
                "brand": 1,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "kia niro"
    assert result2["data"] == {
        "username": "test-username",
        "password": "test-password",
        "region": 1,
        "brand": 1,
        "pin": "",
        "token": {
            "key": "value",
            "valid_until": "1-01-01 00:00:00.000000",
            "vehicle_name": "kia niro",
            "vehicle_id": "123456789",
        },
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "hyundai_kia_connect_api.KiaUvoApiEU.login",
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "region": 1,
                "brand": 1,
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_unexpected_exception(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "hyundai_kia_connect_api.KiaUvoApiEU.login",
        side_effect=Exception("unknown"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "region": 1,
                "brand": 1,
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "unknown"}
