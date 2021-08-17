"""Test the P1 Monitor config flow."""
from unittest.mock import patch

from p1monitor import P1MonitorError

from homeassistant.components.p1_monitor.const import CONF_TIME_BETWEEN_UPDATE, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM

from tests.common import MockConfigEntry


async def test_full_user_flow(hass: HomeAssistant) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == RESULT_TYPE_FORM
    assert result.get("step_id") == SOURCE_USER
    assert "flow_id" in result

    with patch(
        "homeassistant.components.p1_monitor.config_flow.P1Monitor.smartmeter"
    ) as mock_p1monitor, patch(
        "homeassistant.components.p1_monitor.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_NAME: "Name",
                CONF_HOST: "example.com",
            },
        )

    assert result2.get("type") == RESULT_TYPE_CREATE_ENTRY
    assert result2.get("title") == "Name"
    assert result2.get("data") == {
        CONF_HOST: "example.com",
    }

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_p1monitor.mock_calls) == 1


async def test_options_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test config flow options."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result.get("type") == RESULT_TYPE_FORM
    assert result.get("step_id") == "init"
    assert "flow_id" in result

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_TIME_BETWEEN_UPDATE: 10,
        },
    )

    assert result2.get("type") == RESULT_TYPE_CREATE_ENTRY
    assert result2.get("data") == {
        CONF_TIME_BETWEEN_UPDATE: 10,
    }


async def test_api_error(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    with patch(
        "homeassistant.components.p1_monitor.P1Monitor.smartmeter",
        side_effect=P1MonitorError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_NAME: "Name",
                CONF_HOST: "example.com",
            },
        )

    assert result.get("type") == RESULT_TYPE_FORM
    assert result.get("errors") == {"base": "cannot_connect"}
