"""Test the Envisalink config flow."""
from unittest.mock import patch

# from homeassistant.components.envisalink import async_setup
from pyenvisalink.alarm_panel import EnvisalinkAlarmPanel
import pytest

from homeassistant import config_entries
from homeassistant.components.envisalink.const import (
    CONF_ALARM_NAME,
    CONF_PARTITION_SET,
    CONF_ZONE_SET,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


def _get_config_entry_from_unique_id(
    hass: HomeAssistant, unique_id: str
) -> config_entries.ConfigEntry | None:
    for entry in hass.config_entries.async_entries(domain=DOMAIN):
        if entry.unique_id == unique_id:
            return entry
    return None


async def test_form(
    hass: HomeAssistant,
    mock_envisalink_alarm_panel,
    mock_config_data,
    mock_config_data_result,
    mock_unique_id,
) -> None:
    """Test the full manual user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result.get("step_id") == "user"
    assert result.get("type") == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=mock_config_data,
    )

    assert result.get("title") == "TestAlarmName"
    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert "data" in result
    assert result["data"] == mock_config_data_result
    assert "result" in result
    assert result["result"].unique_id == mock_unique_id


@pytest.mark.parametrize(
    "alarm_error,exception_message",
    [
        (EnvisalinkAlarmPanel.ConnectionResult.INVALID_AUTHORIZATION, "invalid_auth"),
        (EnvisalinkAlarmPanel.ConnectionResult.CONNECTION_FAILED, "cannot_connect"),
        ("unknown", "unknown"),
    ],
)
async def test_form_discover_error(
    hass: HomeAssistant, mock_config_data, alarm_error, exception_message
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pyenvisalink.alarm_panel.EnvisalinkAlarmPanel.discover",
        return_value=alarm_error,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=mock_config_data,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": exception_message}


async def test_form_invalid_zone_spec(
    hass: HomeAssistant, mock_envisalink_alarm_panel, mock_config_data
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_config_data[CONF_ZONE_SET] = "garbage"
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=mock_config_data,
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_zone_spec"}


async def test_form_invalid_partition_spec(
    hass: HomeAssistant, mock_envisalink_alarm_panel, mock_config_data
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_config_data[CONF_PARTITION_SET] = "garbage"
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=mock_config_data,
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_partition_spec"}


async def test_form_unexpected_error(hass: HomeAssistant, mock_config_data) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pyenvisalink.alarm_panel.EnvisalinkAlarmPanel.discover",
        side_effect=KeyError("unexpected"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=mock_config_data,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_options_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test options config flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result.get("type") == FlowResultType.MENU
    assert result.get("step_id") == "user"


async def test_options_basic_menu(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test options config flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result.get("type") == FlowResultType.MENU
    assert result.get("step_id") == "user"


async def test_options_basic_form(
    hass: HomeAssistant,
    mock_envisalink_alarm_panel,
    mock_config_entry,
    mock_config_data_result,
    mock_config_data,
    mock_unique_id,
    mock_options_data_dsc,
) -> None:
    """Test the basic options flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id,
        context={"source": "user"},
    )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "basic"}
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "basic"
    assert result["errors"] == {}

    mock_config_data.pop(CONF_ALARM_NAME)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=mock_config_data
    )
    await hass.async_block_till_done()
    entry = _get_config_entry_from_unique_id(hass, mock_unique_id)

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert "data" in result
    assert result["data"] == mock_options_data_dsc
    assert "result" in result
    assert entry.data == mock_config_data_result


async def test_options_basic_form_discovery_error(
    hass: HomeAssistant,
    mock_envisalink_alarm_panel,
    mock_config_entry,
    mock_config_data_result,
    mock_config_data,
    mock_unique_id,
) -> None:
    """Test discover error for the basic options flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id,
        context={"source": "user"},
    )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "basic"}
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "basic"
    assert result["errors"] == {}

    with patch(
        "pyenvisalink.alarm_panel.EnvisalinkAlarmPanel.discover",
        return_value=EnvisalinkAlarmPanel.ConnectionResult.CONNECTION_FAILED,
    ):
        mock_config_data.pop(CONF_ALARM_NAME)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=mock_config_data
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_options_basic_form_unexpected_error(
    hass: HomeAssistant,
    mock_envisalink_alarm_panel,
    mock_config_entry,
    mock_config_data_result,
    mock_config_data,
    mock_unique_id,
) -> None:
    """Test unexpected error for the basic options flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id,
        context={"source": "user"},
    )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "basic"}
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "basic"
    assert result["errors"] == {}

    with patch(
        "pyenvisalink.alarm_panel.EnvisalinkAlarmPanel.discover",
        side_effect=KeyError("unexpected"),
    ):
        mock_config_data.pop(CONF_ALARM_NAME)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=mock_config_data
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_options_advanced_form_dsc(
    hass: HomeAssistant,
    mock_envisalink_alarm_panel,
    mock_config_entry,
    mock_config_data_result,
    mock_config_data,
    mock_unique_id,
    mock_options_data_dsc,
) -> None:
    """Test the advanced options flow for DSC panels."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id,
        context={"source": "user"},
    )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "advanced"}
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "advanced"
    assert result["errors"] == {}

    mock_config_data.pop(CONF_ALARM_NAME)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=mock_options_data_dsc
    )
    await hass.async_block_till_done()
    entry = _get_config_entry_from_unique_id(hass, mock_unique_id)

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert "data" in result
    assert result["data"] == mock_options_data_dsc
    assert "result" in result
    assert entry.data == mock_config_data_result


async def test_options_advanced_form_honeywell(
    hass: HomeAssistant,
    mock_envisalink_alarm_panel,
    mock_config_entry_honeywell,
    mock_config_data_result,
    mock_config_data,
    mock_unique_id,
    mock_options_data_honeywell,
) -> None:
    """Test the advanced options flow for Honeywell panels."""
    mock_config_entry_honeywell.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(
        mock_config_entry_honeywell.entry_id,
        context={"source": "user"},
    )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"next_step_id": "advanced"}
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "advanced"
    assert result["errors"] == {}

    mock_config_data.pop(CONF_ALARM_NAME)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=mock_options_data_honeywell
    )
    await hass.async_block_till_done()
    entry = _get_config_entry_from_unique_id(hass, mock_unique_id)

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert "data" in result
    assert result["data"] == mock_options_data_honeywell
    assert "result" in result
    assert entry.data == mock_config_data_result
