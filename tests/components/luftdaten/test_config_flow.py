"""Define tests for the Luftdaten config flow."""
from unittest.mock import MagicMock, patch

from luftdaten.exceptions import LuftdatenConnectionError

from homeassistant.components.luftdaten import DOMAIN
from homeassistant.components.luftdaten.const import CONF_SENSOR_ID
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_SCAN_INTERVAL, CONF_SHOW_ON_MAP
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from tests.common import MockConfigEntry


async def test_duplicate_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that errors are shown when duplicates are added."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == RESULT_TYPE_FORM
    assert result.get("step_id") == SOURCE_USER
    assert "flow_id" in result

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_SENSOR_ID: 12345},
    )

    assert result2.get("type") == RESULT_TYPE_ABORT
    assert result2.get("reason") == "already_configured"


async def test_communication_error(hass: HomeAssistant) -> None:
    """Test that no sensor is added while unable to communicate with API."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == RESULT_TYPE_FORM
    assert result.get("step_id") == SOURCE_USER
    assert "flow_id" in result

    with patch("luftdaten.Luftdaten.get_data", side_effect=LuftdatenConnectionError):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_SENSOR_ID: 12345},
        )

    assert result2.get("type") == RESULT_TYPE_FORM
    assert result2.get("step_id") == SOURCE_USER
    assert result2.get("errors") == {CONF_SENSOR_ID: "cannot_connect"}


async def test_invalid_sensor(hass: HomeAssistant) -> None:
    """Test that an invalid sensor throws an error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == RESULT_TYPE_FORM
    assert result.get("step_id") == SOURCE_USER
    assert "flow_id" in result

    with patch("luftdaten.Luftdaten.get_data", return_value=False), patch(
        "luftdaten.Luftdaten.validate_sensor", return_value=False
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_SENSOR_ID: 12345},
        )

    assert result2.get("type") == RESULT_TYPE_FORM
    assert result2.get("step_id") == SOURCE_USER
    assert result2.get("errors") == {CONF_SENSOR_ID: "invalid_sensor"}


async def test_step_user(hass: HomeAssistant, mock_setup_entry: MagicMock) -> None:
    """Test that the user step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == RESULT_TYPE_FORM
    assert result.get("step_id") == SOURCE_USER
    assert "flow_id" in result

    with patch("luftdaten.Luftdaten.get_data", return_value=True), patch(
        "luftdaten.Luftdaten.validate_sensor", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_SENSOR_ID: 12345,
                CONF_SHOW_ON_MAP: False,
            },
        )

    assert result2.get("type") == RESULT_TYPE_CREATE_ENTRY
    assert result2.get("title") == "12345"
    assert result2.get("data") == {
        CONF_SENSOR_ID: 12345,
        CONF_SHOW_ON_MAP: False,
        CONF_SCAN_INTERVAL: 600.0,
    }
