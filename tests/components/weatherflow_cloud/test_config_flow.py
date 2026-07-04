"""Test the WeatherflowCloud config flow."""

import pytest

from homeassistant import config_entries
from homeassistant.components.weatherflow_cloud.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_config(hass: HomeAssistant, mock_get_stations) -> None:
    """Test the config flow for the ideal case."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_TOKEN: "string",
        },
    )

    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_config_flow_abort(hass: HomeAssistant, mock_get_stations) -> None:
    """Test an abort case."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_TOKEN: "same_same",
        },
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_TOKEN: "same_same",
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("mock_fixture", "expected_error"),
    [
        ("mock_get_stations_500_error", "cannot_connect"),
        ("mock_get_stations_401_error", "invalid_api_key"),
    ],
)
async def test_config_errors(
    hass: HomeAssistant,
    request: pytest.FixtureRequest,
    expected_error: str,
    mock_fixture: str,
    mock_get_stations,
) -> None:
    """Test the config flow for various error scenarios."""
    mock_get_stations_bad = request.getfixturevalue(mock_fixture)
    with mock_get_stations_bad:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_TOKEN: "string"},
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": expected_error}

    with mock_get_stations:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_TOKEN: "string"},
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_reauth(hass: HomeAssistant, mock_get_stations_401_error) -> None:
    """Test a reauth_flow."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_TOKEN: "same_same",
        },
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_TOKEN: "SAME_SAME"}
    )

    assert result["reason"] == "reauth_successful"
    assert result["type"] is FlowResultType.ABORT
    assert entry.data[CONF_API_TOKEN] == "SAME_SAME"
