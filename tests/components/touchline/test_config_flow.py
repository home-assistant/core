"""Test the touchline config flow."""

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_HOST


@pytest.fixture(name="setup")
def mock_controller_setup():
    """Mock controller setup."""
    with patch(
        "homeassistant.components.touchline.async_setup_entry", return_value=True
    ):
        yield


async def test_form_successful(hass):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        "touchline", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {} or result["errors"] is None

    with (
        patch(
            "homeassistant.components.touchline.config_flow._try_connect_and_fetch_basic_info",
            return_value={"type": "success", "data": {}},
        ),
        patch(
            "homeassistant.components.touchline.async_setup_entry",
            return_value=True,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "http://1.1.1.1",
            },
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "http://1.1.1.1"
    assert result2["data"] == {
        CONF_HOST: "http://1.1.1.1",
    }


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        "touchline", context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.touchline.config_flow._try_connect_and_fetch_basic_info",
        return_value={"type": "cannot_connect", "data": {}},
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}
