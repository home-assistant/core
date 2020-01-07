"""Test the National Weather Service config flow."""
from unittest.mock import patch

from homeassistant import config_entries, setup
from homeassistant.components.nws import unique_id
from homeassistant.components.nws.config_flow import CannotConnect
from homeassistant.components.nws.const import DOMAIN

from .helpers.pynws import mock_nws

from tests.common import mock_coro


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.nws.config_flow.validate_input",
        return_value=mock_coro((["ABC"], {"title": "test"})),
    ), patch(
        "homeassistant.components.nws.async_setup", return_value=mock_coro(True)
    ) as mock_setup, patch(
        "homeassistant.components.nws.async_setup_entry", return_value=mock_coro(True),
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"latitude": 50.0, "longitude": -75.0, "api_key": "test_key"},
        )

        assert result2["type"] == "form"

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {"station": "ABC"},
        )

        assert result3["type"] == "create_entry"
        assert result3["title"] == unique_id(50.0, -75.0)
        assert result3["data"] == {
            "latitude": 50.0,
            "longitude": -75.0,
            "api_key": "test_key",
            "station": "ABC",
        }

        await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nws.config_flow.validate_input",
        side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"latitude": 50, "longitude": -75, "api_key": "test_key"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_duplicate_entry(hass):
    """Test we handle cannot have duplicate entries."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    MockNws = mock_nws()
    with patch(
        "homeassistant.components.nws.SimpleNWS", return_value=MockNws(),
    ), patch(
        "homeassistant.components.nws.config_flow.SimpleNWS", return_value=MockNws(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"latitude": 50, "longitude": -75, "api_key": "test_key"},
        )
        await hass.config_entries.flow.async_configure(
            result2["flow_id"], {"station": "ABC"},
        )

        result_entry2 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result2_entry2 = await hass.config_entries.flow.async_configure(
            result_entry2["flow_id"],
            {"latitude": 50, "longitude": -75, "api_key": "test_key"},
        )

        await hass.async_block_till_done()

    assert result2_entry2["type"] == "form"
    assert result2_entry2["errors"] == {"base": "already_configured"}
