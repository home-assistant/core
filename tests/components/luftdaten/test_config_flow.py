"""Define tests for the Luftdaten config flow."""
from unittest.mock import MagicMock

from luftdaten.exceptions import LuftdatenConnectionError

from homeassistant.components.luftdaten import DOMAIN
from homeassistant.components.luftdaten.const import CONF_SENSOR_ID
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_SHOW_ON_MAP
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_duplicate_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that errors are shown when duplicates are added."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == SOURCE_USER

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_SENSOR_ID: 12345},
    )

    assert result2.get("type") == FlowResultType.ABORT
    assert result2.get("reason") == "already_configured"


async def test_communication_error(
    hass: HomeAssistant, mock_luftdaten_config_flow: MagicMock
) -> None:
    """Test that no sensor is added while unable to communicate with API."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == SOURCE_USER

    mock_luftdaten_config_flow.get_data.side_effect = LuftdatenConnectionError
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_SENSOR_ID: 12345},
    )

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == SOURCE_USER
    assert result2.get("errors") == {CONF_SENSOR_ID: "cannot_connect"}

    mock_luftdaten_config_flow.get_data.side_effect = None
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={CONF_SENSOR_ID: 12345},
    )

    assert result3.get("type") == FlowResultType.CREATE_ENTRY
    assert result3.get("title") == "12345"
    assert result3.get("data") == {
        CONF_SENSOR_ID: 12345,
        CONF_SHOW_ON_MAP: False,
    }


async def test_invalid_sensor(
    hass: HomeAssistant, mock_luftdaten_config_flow: MagicMock
) -> None:
    """Test that an invalid sensor throws an error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == SOURCE_USER

    mock_luftdaten_config_flow.validate_sensor.return_value = False
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_SENSOR_ID: 11111},
    )

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == SOURCE_USER
    assert result2.get("errors") == {CONF_SENSOR_ID: "invalid_sensor"}

    mock_luftdaten_config_flow.validate_sensor.return_value = True
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={CONF_SENSOR_ID: 12345},
    )

    assert result3.get("type") == FlowResultType.CREATE_ENTRY
    assert result3.get("title") == "12345"
    assert result3.get("data") == {
        CONF_SENSOR_ID: 12345,
        CONF_SHOW_ON_MAP: False,
    }


async def test_step_user(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
    mock_luftdaten_config_flow: MagicMock,
) -> None:
    """Test that the user step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == SOURCE_USER

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_SENSOR_ID: 12345,
            CONF_SHOW_ON_MAP: True,
        },
    )

    assert result2.get("type") == FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "12345"
    assert result2.get("data") == {
        CONF_SENSOR_ID: 12345,
        CONF_SHOW_ON_MAP: True,
    }
