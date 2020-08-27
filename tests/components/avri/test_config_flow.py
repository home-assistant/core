"""Test the Avri config flow."""
from homeassistant import config_entries, setup
from homeassistant.components.avri.const import DOMAIN

from tests.async_mock import patch


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "avri", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.avri.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "zip_code": "1234AB",
                "house_number": 42,
                "house_number_extension": "",
                "country_code": "NL",
            },
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "1234AB 42"
    assert result2["data"] == {
        "id": "1234AB 42",
        "zip_code": "1234AB",
        "house_number": 42,
        "house_number_extension": "",
        "country_code": "NL",
    }
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_house_number(hass):
    """Test we handle invalid house number."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "zip_code": "1234AB",
            "house_number": -1,
            "house_number_extension": "",
            "country_code": "NL",
        },
    )

    assert result2["type"] == "form"
    assert result2["errors"] == {"house_number": "invalid_house_number"}


async def test_form_invalid_country_code(hass):
    """Test we handle invalid county code."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "zip_code": "1234AB",
            "house_number": 42,
            "house_number_extension": "",
            "country_code": "foo",
        },
    )

    assert result2["type"] == "form"
    assert result2["errors"] == {"country_code": "invalid_country_code"}
