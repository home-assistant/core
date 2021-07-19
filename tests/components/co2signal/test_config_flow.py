"""Test the CO2 Signal config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries, setup
from homeassistant.components.co2signal import DOMAIN, config_flow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM
from homeassistant.setup import async_setup_component

from . import VALID_PAYLOAD

from tests.common import MockConfigEntry


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


@pytest.mark.parametrize(
    "err_str,err_code",
    [
        ("Invalid authentication credentials", "invalid_auth"),
        ("API rate limit exceeded.", "api_ratelimit"),
        ("Something else", "unknown"),
    ],
)
async def test_form_error_handling(hass: HomeAssistant, err_str, err_code) -> None:
    """Test we handle expected errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.co2signal.config_flow.CO2Signal.get_latest",
        side_effect=ValueError(err_str),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "location": config_flow.TYPE_USE_HOME,
                "api_key": "api_key",
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": err_code}


async def test_form_error_unexpected_error(hass: HomeAssistant) -> None:
    """Test we handle unexpected error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.co2signal.config_flow.CO2Signal.get_latest",
        side_effect=Exception("Boom"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "location": config_flow.TYPE_USE_HOME,
                "api_key": "api_key",
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_error_unexpected_data(hass: HomeAssistant) -> None:
    """Test we handle unexpected data."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.co2signal.config_flow.CO2Signal.get_latest",
        return_value={"status": "error"},
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "location": config_flow.TYPE_USE_HOME,
                "api_key": "api_key",
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "unknown"}


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


async def test_import_abort_existing_home(hass: HomeAssistant) -> None:
    """Test we abort if home entry found."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    MockConfigEntry(domain="co2signal", data={"api_key": "abcd"}).add_to_hass(hass)

    with patch(
        "homeassistant.components.co2signal.config_flow.CO2Signal.get_latest",
        return_value=VALID_PAYLOAD,
    ):
        assert await async_setup_component(
            hass, "sensor", {"sensor": {"platform": "co2signal", "token": "1234"}}
        )
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries("co2signal")) == 1


async def test_import_abort_existing_country(hass: HomeAssistant) -> None:
    """Test we abort if existing country found."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    MockConfigEntry(
        domain="co2signal", data={"api_key": "abcd", "country_code": "nl"}
    ).add_to_hass(hass)

    with patch(
        "homeassistant.components.co2signal.config_flow.CO2Signal.get_latest",
        return_value=VALID_PAYLOAD,
    ):
        assert await async_setup_component(
            hass,
            "sensor",
            {
                "sensor": {
                    "platform": "co2signal",
                    "token": "1234",
                    "country_code": "nl",
                }
            },
        )
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries("co2signal")) == 1


async def test_import_abort_existing_coordinates(hass: HomeAssistant) -> None:
    """Test we abort if existing coordinates found."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    MockConfigEntry(
        domain="co2signal", data={"api_key": "abcd", "latitude": 1, "longitude": 2}
    ).add_to_hass(hass)

    with patch(
        "homeassistant.components.co2signal.config_flow.CO2Signal.get_latest",
        return_value=VALID_PAYLOAD,
    ):
        assert await async_setup_component(
            hass,
            "sensor",
            {
                "sensor": {
                    "platform": "co2signal",
                    "token": "1234",
                    "latitude": 1,
                    "longitude": 2,
                }
            },
        )
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries("co2signal")) == 1
