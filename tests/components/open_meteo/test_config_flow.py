"""Tests for the Open-Meteo config flow."""

import pytest

from homeassistant.components.open_meteo.const import (
    CONF_FORECAST_DAYS,
    DEFAULT_FORECAST_DAYS,
    DOMAIN,
    FORECAST_DAY_LIMITS,
)
from homeassistant.components.zone import ENTITY_ID_HOME
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ZONE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_user_flow(hass: HomeAssistant) -> None:
    """Test the full user configuration flow with the default forecast limit."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ZONE: ENTITY_ID_HOME},
    )

    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "test home"
    assert result2.get("data") == {CONF_ZONE: ENTITY_ID_HOME}
    assert result2.get("options") == {CONF_FORECAST_DAYS: DEFAULT_FORECAST_DAYS}


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize("forecast_days", list(FORECAST_DAY_LIMITS))
async def test_user_flow_forecast_days(hass: HomeAssistant, forecast_days: str) -> None:
    """Test the forecast limit chosen during setup is stored in options."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ZONE: ENTITY_ID_HOME, CONF_FORECAST_DAYS: forecast_days},
    )

    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2.get("data") == {CONF_ZONE: ENTITY_ID_HOME}
    assert result2.get("options") == {CONF_FORECAST_DAYS: forecast_days}


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    "invalid_choice",
    [
        pytest.param("unsupported", id="unknown-choice"),
        pytest.param("-1", id="negative-choice"),
        pytest.param(3, id="wrong-type"),
    ],
)
async def test_user_flow_invalid_forecast_days(
    hass: HomeAssistant, invalid_choice: str | int
) -> None:
    """Test an unsupported setup choice is rejected and can be corrected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_ZONE: ENTITY_ID_HOME, CONF_FORECAST_DAYS: invalid_choice},
        )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ZONE: ENTITY_ID_HOME, CONF_FORECAST_DAYS: "3"},
    )

    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2.get("options") == {CONF_FORECAST_DAYS: "3"}


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    "invalid_choice",
    [
        pytest.param("unsupported", id="unknown-choice"),
        pytest.param("-1", id="negative-choice"),
        pytest.param(3, id="wrong-type"),
    ],
)
async def test_forecast_days_options_invalid_input(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    invalid_choice: str | int,
) -> None:
    """Reject invalid input and allow correction in the same options flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    flow_id = result["flow_id"]

    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(
            flow_id,
            user_input={CONF_FORECAST_DAYS: invalid_choice},
        )

    assert mock_config_entry.options == {}

    result = await hass.config_entries.options.async_configure(
        flow_id,
        user_input={CONF_FORECAST_DAYS: "3"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert mock_config_entry.options == {CONF_FORECAST_DAYS: "3"}


@pytest.mark.parametrize(
    ("stored_options", "expected_choice"),
    [
        pytest.param({}, "all", id="missing-option"),
        pytest.param(
            {CONF_FORECAST_DAYS: "3"},
            "3",
            id="saved-choice",
        ),
        pytest.param(
            {CONF_FORECAST_DAYS: "unsupported"},
            "all",
            id="unknown-choice",
        ),
        pytest.param(
            {CONF_FORECAST_DAYS: ["3"]},
            "all",
            id="invalid-type",
        ),
    ],
)
async def test_forecast_days_options_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    stored_options: dict[str, object],
    expected_choice: str,
) -> None:
    """Show a valid default without changing stored options when opened."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options=stored_options,
    )

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["data_schema"]({}) == {
        CONF_FORECAST_DAYS: expected_choice,
    }
    assert mock_config_entry.options == stored_options
