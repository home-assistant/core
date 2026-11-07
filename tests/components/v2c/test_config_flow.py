"""Test the V2C config flow."""

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytrydan.exceptions import TrydanError

from homeassistant.components.v2c.const import CONF_PV_AVAILABLE, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_full_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_v2c_client: AsyncMock
) -> None:
    """Test we can finish a config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "EVSE 1.1.1.1"
    assert result["data"] == {CONF_HOST: "1.1.1.1"}
    assert result["result"].unique_id == "ABC123"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize("pv_available", [True, False])
@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    pv_available: bool,
) -> None:
    """Test configuring photovoltaic availability."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_PV_AVAILABLE: pv_available}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {CONF_PV_AVAILABLE: pv_available}


@pytest.mark.usefixtures("mock_v2c_client")
async def test_options_reload_entities(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test updating the options reloads the mode selector."""
    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.SELECT]):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        assert hass.states.get("select.evse_1_1_1_1_dynamic_power_mode") is None

        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )
        await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_PV_AVAILABLE: True}
        )
        await hass.async_block_till_done()
        assert hass.states.get("select.evse_1_1_1_1_dynamic_power_mode") is not None

        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )
        await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_PV_AVAILABLE: False}
        )
        await hass.async_block_till_done()
        assert hass.states.is_state(
            "select.evse_1_1_1_1_dynamic_power_mode", STATE_UNAVAILABLE
        )


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (TrydanError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_cannot_connect(
    hass: HomeAssistant, side_effect: Exception, error: str, mock_v2c_client: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    mock_v2c_client.get_data.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    mock_v2c_client.get_data.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "1.1.1.1"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "EVSE 1.1.1.1"
    assert result["data"] == {CONF_HOST: "1.1.1.1"}
