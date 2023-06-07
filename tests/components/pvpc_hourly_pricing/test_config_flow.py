"""Tests for the pvpc_hourly_pricing config_flow."""
from datetime import datetime, timedelta

from freezegun import freeze_time

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.pvpc_hourly_pricing import (
    ATTR_POWER,
    ATTR_POWER_P3,
    ATTR_TARIFF,
    DOMAIN,
    TARIFFS,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .conftest import check_valid_state

from tests.common import async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker

_MOCK_TIME_VALID_RESPONSES = datetime(2023, 1, 6, 12, 0, tzinfo=dt_util.UTC)


async def test_config_flow(
    hass: HomeAssistant, pvpc_aioclient_mock: AiohttpClientMocker
) -> None:
    """Test config flow for pvpc_hourly_pricing.

    - Create a new entry with tariff "2.0TD (Ceuta/Melilla)"
    - Check state and attributes
    - Check abort when trying to config another with same tariff
    - Check removal and add again to check state restoration
    - Configure options to change power and tariff to "2.0TD"
    """
    hass.config.set_time_zone("Europe/Madrid")
    tst_config = {
        CONF_NAME: "test",
        ATTR_TARIFF: TARIFFS[1],
        ATTR_POWER: 4.6,
        ATTR_POWER_P3: 5.75,
    }

    with freeze_time(_MOCK_TIME_VALID_RESPONSES) as mock_time:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], tst_config
        )
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

        await hass.async_block_till_done()
        state = hass.states.get("sensor.test")
        check_valid_state(state, tariff=TARIFFS[1])
        assert pvpc_aioclient_mock.call_count == 1

        # Check abort when configuring another with same tariff
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], tst_config
        )
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert pvpc_aioclient_mock.call_count == 1

        # Check removal
        registry = er.async_get(hass)
        registry_entity = registry.async_get("sensor.test")
        assert await hass.config_entries.async_remove(registry_entity.config_entry_id)

        # and add it again with UI
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], tst_config
        )
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

        await hass.async_block_till_done()
        state = hass.states.get("sensor.test")
        check_valid_state(state, tariff=TARIFFS[1])
        assert pvpc_aioclient_mock.call_count == 2
        assert state.attributes["period"] == "P3"
        assert state.attributes["next_period"] == "P2"
        assert state.attributes["available_power"] == 5750

        # check options flow
        current_entries = hass.config_entries.async_entries(DOMAIN)
        assert len(current_entries) == 1
        config_entry = current_entries[0]

        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={ATTR_POWER: 3.0, ATTR_POWER_P3: 4.6},
        )
        await hass.async_block_till_done()
        state = hass.states.get("sensor.test")
        check_valid_state(state, tariff=TARIFFS[1])
        assert pvpc_aioclient_mock.call_count == 3
        assert state.attributes["period"] == "P3"
        assert state.attributes["next_period"] == "P2"
        assert state.attributes["available_power"] == 4600

        # check update failed
        ts_future = _MOCK_TIME_VALID_RESPONSES + timedelta(days=1)
        mock_time.move_to(ts_future)
        async_fire_time_changed(hass, ts_future)
        await hass.async_block_till_done()
        state = hass.states.get("sensor.test")
        check_valid_state(state, tariff=TARIFFS[0], value="unavailable")
        assert "period" not in state.attributes
        assert pvpc_aioclient_mock.call_count == 4
