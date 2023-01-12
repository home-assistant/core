"""Tests for the pvpc_hourly_pricing config_flow."""
from datetime import datetime, timedelta

from freezegun.api import FrozenDateTimeFactory

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.pvpc_hourly_pricing.const import (
    ATTR_POWER,
    ATTR_POWER_P3,
    ATTR_TARIFF,
    CONF_USE_API_TOKEN,
    DOMAIN,
    TARIFFS,
)
from homeassistant.const import CONF_API_TOKEN, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .conftest import check_valid_state

from tests.common import async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker

_MOCK_TIME_VALID_RESPONSES = datetime(2023, 1, 6, 12, 0, tzinfo=dt_util.UTC)
_MOCK_TIME_BAD_AUTH_RESPONSES = datetime(2023, 1, 8, 12, 0, tzinfo=dt_util.UTC)


async def test_config_flow(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    pvpc_aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test config flow for pvpc_hourly_pricing.

    - Create a new entry with tariff "2.0TD (Ceuta/Melilla)"
    - Check state and attributes
    - Check abort when trying to config another with same tariff
    - Check removal and add again to check state restoration
    - Configure options to introduce API Token, with bad auth and good one
    """
    freezer.move_to(_MOCK_TIME_VALID_RESPONSES)
    hass.config.set_time_zone("Europe/Madrid")
    tst_config = {
        CONF_NAME: "test",
        ATTR_TARIFF: TARIFFS[1],
        ATTR_POWER: 4.6,
        ATTR_POWER_P3: 5.75,
        CONF_USE_API_TOKEN: False,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], tst_config
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

    await hass.async_block_till_done()
    state = hass.states.get("sensor.esios_pvpc")
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
    registry_entity = registry.async_get("sensor.esios_pvpc")
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
    state = hass.states.get("sensor.esios_pvpc")
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
        user_input={ATTR_POWER: 3.0, ATTR_POWER_P3: 4.6, CONF_USE_API_TOKEN: True},
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "api_token"
    assert pvpc_aioclient_mock.call_count == 2

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_API_TOKEN: "good-token"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert pvpc_aioclient_mock.call_count == 2
    await hass.async_block_till_done()
    state = hass.states.get("sensor.esios_pvpc")
    check_valid_state(state, tariff=TARIFFS[1])
    assert pvpc_aioclient_mock.call_count == 3
    assert state.attributes["period"] == "P3"
    assert state.attributes["next_period"] == "P2"
    assert state.attributes["available_power"] == 4600

    # check update failed
    freezer.tick(timedelta(days=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.esios_pvpc")
    check_valid_state(state, tariff=TARIFFS[0], value="unavailable")
    assert "period" not in state.attributes
    assert pvpc_aioclient_mock.call_count == 4

    # disable api token in options
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={ATTR_POWER: 3.0, ATTR_POWER_P3: 4.6, CONF_USE_API_TOKEN: False},
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert pvpc_aioclient_mock.call_count == 4
    await hass.async_block_till_done()


async def test_reauth(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    pvpc_aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test reauth flow for API-token mode."""
    freezer.move_to(_MOCK_TIME_BAD_AUTH_RESPONSES)
    hass.config.set_time_zone("Europe/Madrid")
    tst_config = {
        CONF_NAME: "test",
        ATTR_TARIFF: TARIFFS[1],
        ATTR_POWER: 4.6,
        ATTR_POWER_P3: 5.75,
        CONF_USE_API_TOKEN: True,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], tst_config
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "api_token"
    assert pvpc_aioclient_mock.call_count == 0

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_TOKEN: "bad-token"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "api_token"
    assert result["errors"]["base"] == "invalid_auth"
    assert pvpc_aioclient_mock.call_count == 1

    freezer.move_to(_MOCK_TIME_VALID_RESPONSES)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_TOKEN: "good-token"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    config_entry = result["result"]
    assert pvpc_aioclient_mock.call_count == 3

    # check reauth trigger with bad-auth responses
    freezer.move_to(_MOCK_TIME_BAD_AUTH_RESPONSES)
    await hass.async_block_till_done()
    assert pvpc_aioclient_mock.call_count == 4

    result = hass.config_entries.flow.async_progress_by_handler(DOMAIN)[0]
    assert result["context"]["entry_id"] == config_entry.entry_id
    assert result["context"]["source"] == config_entries.SOURCE_REAUTH
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_TOKEN: "bad-token"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert pvpc_aioclient_mock.call_count == 5

    result = hass.config_entries.flow.async_progress_by_handler(DOMAIN)[0]
    assert result["context"]["entry_id"] == config_entry.entry_id
    assert result["context"]["source"] == config_entries.SOURCE_REAUTH
    assert result["step_id"] == "reauth_confirm"

    freezer.move_to(_MOCK_TIME_VALID_RESPONSES)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_TOKEN: "good-token"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert pvpc_aioclient_mock.call_count == 6

    await hass.async_block_till_done()
    assert pvpc_aioclient_mock.call_count == 7
