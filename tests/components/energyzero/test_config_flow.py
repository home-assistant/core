"""Test the EnergyZero config flow."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.energyzero.const import (
    CONF_ELECTRICITY_PRICE_INTERVAL,
    DOMAIN,
    ELECTRICITY_INTERVALS,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_full_user_flow(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert "flow_id" in result

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "EnergyZero"
    assert result2.get("data") == {}

    assert len(mock_setup_entry.mock_calls) == 1


async def test_single_instance(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test abort when setting up a duplicate entry."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "single_instance_allowed"


@pytest.mark.freeze_time("2026-04-10 20:32:59")
@pytest.mark.parametrize("initial", [None, "hourly", "quarter_hourly"])
@pytest.mark.parametrize("selected", ["hourly", "quarter_hourly"])
@pytest.mark.usefixtures("mock_energyzero")
async def test_options_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    initial: str | None,
    selected: str,
) -> None:
    """Test defaults, saved options and automatic reload on changes."""
    options = {} if initial is None else {CONF_ELECTRICITY_PRICE_INTERVAL: initial}
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, options=options)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    schema = result["data_schema"]
    assert schema({}) == {CONF_ELECTRICITY_PRICE_INTERVAL: "hourly"}
    key = next(iter(schema.schema))
    assert (key.description or {}).get("suggested_value", "hourly") == (
        initial or "hourly"
    )

    with patch.object(hass.config_entries, "async_reload", return_value=True) as reload:
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_ELECTRICITY_PRICE_INTERVAL: selected},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {CONF_ELECTRICITY_PRICE_INTERVAL: selected}
    assert reload.call_count == (initial != selected)


@pytest.mark.freeze_time("2026-04-10 20:32:59")
@pytest.mark.parametrize("selected", ["hourly", "quarter_hourly"])
async def test_options_reload(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_energyzero: MagicMock,
    selected: str,
) -> None:
    """Apply changed options to both requests without recreating entities."""
    original_entities = set(hass.states.async_entity_ids("sensor"))
    mock_energyzero.get_electricity_prices.reset_mock()
    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_ELECTRICITY_PRICE_INTERVAL: selected}
    )
    await hass.async_block_till_done()
    assert set(hass.states.async_entity_ids("sensor")) == original_entities
    assert mock_energyzero.get_electricity_prices.await_count == 2
    assert all(
        request.kwargs["interval"] == ELECTRICITY_INTERVALS[selected]
        for request in mock_energyzero.get_electricity_prices.await_args_list
    )
