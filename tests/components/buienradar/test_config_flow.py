"""Test the buienradar2 config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.buienradar.const import DOMAIN
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE

from tests.common import MockConfigEntry

TEST_LATITUDE = 51.5288504
TEST_LONGITUDE = 5.4002156


async def test_config_flow_setup_(hass):
    """Test setup of camera."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.buienradar.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_LATITUDE: TEST_LATITUDE, CONF_LONGITUDE: TEST_LONGITUDE},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == f"{TEST_LATITUDE},{TEST_LONGITUDE}"
    assert result["data"] == {
        CONF_LATITUDE: TEST_LATITUDE,
        CONF_LONGITUDE: TEST_LONGITUDE,
    }


async def test_config_flow_already_configured_weather(hass):
    """Test already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_LATITUDE: TEST_LATITUDE,
            CONF_LONGITUDE: TEST_LONGITUDE,
        },
        unique_id=DOMAIN,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_LATITUDE: TEST_LATITUDE, CONF_LONGITUDE: TEST_LONGITUDE},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "already_configured"}


async def test_import_camera(hass):
    """Test import of camera."""

    with patch(
        "homeassistant.components.buienradar.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_LATITUDE: TEST_LATITUDE, CONF_LONGITUDE: TEST_LONGITUDE},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == f"{TEST_LATITUDE},{TEST_LONGITUDE}"
    assert result["data"] == {
        CONF_LATITUDE: TEST_LATITUDE,
        CONF_LONGITUDE: TEST_LONGITUDE,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={CONF_LATITUDE: TEST_LATITUDE, CONF_LONGITUDE: TEST_LONGITUDE},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
