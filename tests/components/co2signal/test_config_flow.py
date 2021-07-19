"""Test the CO2 Signal config flow."""
from unittest.mock import patch

from homeassistant import config_entries, setup
from homeassistant.components.co2signal import DOMAIN, config_flow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM
from homeassistant.setup import async_setup_component

from . import VALID_PAYLOAD


async def test_form_home(hass: HomeAssistant) -> None:
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.co2signal.config_flow.CO2Signal.get_latest",
        return_value=VALID_PAYLOAD,
    ), patch(
        "homeassistant.components.co2signal.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "location": config_flow.TYPE_USE_HOME,
                "api_key": "api_key",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "CO2 Signal"
    assert result2["data"] == {
        "api_key": "api_key",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_coordinates(hass: HomeAssistant) -> None:
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "location": config_flow.TYPE_SPECIFY_COORDINATES,
            "api_key": "api_key",
        },
    )
    assert result2["type"] == RESULT_TYPE_FORM

    with patch(
        "homeassistant.components.co2signal.config_flow.CO2Signal.get_latest",
        return_value=VALID_PAYLOAD,
    ), patch(
        "homeassistant.components.co2signal.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                "latitude": 12.3,
                "longitude": 45.6,
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result3["title"] == "12.3, 45.6"
    assert result3["data"] == {
        "latitude": 12.3,
        "longitude": 45.6,
        "api_key": "api_key",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_country(hass: HomeAssistant) -> None:
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "location": config_flow.TYPE_SPECIFY_COUNTRY,
            "api_key": "api_key",
        },
    )
    assert result2["type"] == RESULT_TYPE_FORM

    with patch(
        "homeassistant.components.co2signal.config_flow.CO2Signal.get_latest",
        return_value=VALID_PAYLOAD,
    ), patch(
        "homeassistant.components.co2signal.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                "country_code": "fr",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result3["title"] == "fr"
    assert result3["data"] == {
        "country_code": "fr",
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
                "location": config_flow.TYPE_USE_HOME,
                "api_key": "api_key",
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_import(hass: HomeAssistant) -> None:
    """Test we import correctly."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch(
        "homeassistant.components.co2signal.config_flow.CO2Signal.get_latest",
        return_value=VALID_PAYLOAD,
    ):
        assert await async_setup_component(
            hass, "sensor", {"sensor": {"platform": "co2signal", "token": "1234"}}
        )
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries("co2signal")) == 1
    state = hass.states.get("sensor.co2_intensity")
    assert state is not None
    assert state.state == "45.99"
    assert state.name == "CO2 intensity"
