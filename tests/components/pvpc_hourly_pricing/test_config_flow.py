"""Tests for the pvpc_hourly_pricing config_flow."""
from datetime import datetime

from freezegun import freeze_time

from homeassistant.components.pvpc_hourly_pricing.const import (
    ATTR_POWER,
    ATTR_POWER_P3,
    ATTR_TARIFF,
    CONF_USE_API_TOKEN,
    DOMAIN,
    TARIFFS,
)
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_API_TOKEN, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from .conftest import check_valid_state

from tests.common import date_util
from tests.test_util.aiohttp import AiohttpClientMocker

_MOCK_TIME_VALID_RESPONSES = datetime(2023, 1, 6, 12, 0, tzinfo=date_util.UTC)
_MOCK_TIME_BAD_AUTH_RESPONSES = datetime(2023, 1, 9, 12, 0, tzinfo=date_util.UTC)
_BAD_TOKEN = {CONF_USE_API_TOKEN: True, CONF_API_TOKEN: "bad-token"}
_GOOD_TOKEN = {CONF_USE_API_TOKEN: True, CONF_API_TOKEN: "good-token"}


async def test_config_flow(
    hass: HomeAssistant, pvpc_aioclient_mock: AiohttpClientMocker
):
    """
    Test config flow for pvpc_hourly_pricing.

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
        CONF_USE_API_TOKEN: False,
    }

    with freeze_time(_MOCK_TIME_VALID_RESPONSES):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], tst_config
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY

        await hass.async_block_till_done()
        state = hass.states.get("sensor.test")
        check_valid_state(state, tariff=TARIFFS[1])
        assert pvpc_aioclient_mock.call_count == 1

        state_inyection = hass.states.get("sensor.injection_price")
        assert state_inyection is None

        # Check abort when configuring another with same tariff
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], tst_config
        )
        assert result["type"] == FlowResultType.ABORT
        assert pvpc_aioclient_mock.call_count == 1

        # Check removal
        registry = er.async_get(hass)
        registry_entity = registry.async_get("sensor.test")
        assert await hass.config_entries.async_remove(registry_entity.config_entry_id)

        # and add it again with UI
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], tst_config
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY

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
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={ATTR_POWER: 3.0, ATTR_POWER_P3: 4.6, CONF_USE_API_TOKEN: True},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "api_token"
        assert pvpc_aioclient_mock.call_count == 2

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_API_TOKEN: "good-token"}
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert pvpc_aioclient_mock.call_count == 2
        await hass.async_block_till_done()
        assert pvpc_aioclient_mock.call_count == 6

        state = hass.states.get("sensor.test")
        check_valid_state(state, tariff=TARIFFS[1])
        assert pvpc_aioclient_mock.call_count == 6
        assert state.attributes["period"] == "P3"
        assert state.attributes["next_period"] == "P2"
        assert state.attributes["available_power"] == 4600

        state_inyection = hass.states.get("sensor.injection_price")
        state_mag = hass.states.get("sensor.mag_tax")
        state_omie = hass.states.get("sensor.omie_price")
        assert state_inyection
        assert state_mag
        assert state_omie
        assert "period" not in state_inyection.attributes
        assert "available_power" not in state_inyection.attributes
        assert "period" not in state_mag.attributes
        assert "period" not in state_omie.attributes

        assert state.attributes["available_power"] == 4600

        # disable api token in options
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={ATTR_POWER: 3.0, ATTR_POWER_P3: 4.6, CONF_USE_API_TOKEN: False},
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert pvpc_aioclient_mock.call_count == 6
        await hass.async_block_till_done()

        state = hass.states.get("sensor.test")
        state_inyection = hass.states.get("sensor.injection_price")
        state_mag = hass.states.get("sensor.mag_tax")
        state_omie = hass.states.get("sensor.omie_price")
        check_valid_state(state, tariff=TARIFFS[1])
        assert state_inyection.state == "unavailable"
        assert state_mag.state == "unavailable"
        assert state_omie.state == "unavailable"


async def test_reauth(
    hass: HomeAssistant, pvpc_aioclient_mock: AiohttpClientMocker
) -> None:
    """Test reauth flow."""
    hass.config.set_time_zone("Europe/Madrid")
    tst_config = {
        CONF_NAME: "test",
        ATTR_TARIFF: TARIFFS[1],
        ATTR_POWER: 4.6,
        ATTR_POWER_P3: 5.75,
        CONF_USE_API_TOKEN: True,
    }
    with freeze_time(_MOCK_TIME_BAD_AUTH_RESPONSES):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], tst_config
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "api_token"
        assert pvpc_aioclient_mock.call_count == 0

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=_BAD_TOKEN
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "api_token"
        assert result["errors"]["base"] == "invalid_auth"
        assert pvpc_aioclient_mock.call_count == 1

    with freeze_time(_MOCK_TIME_VALID_RESPONSES):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=_GOOD_TOKEN
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        config_entry = result["result"]
        assert pvpc_aioclient_mock.call_count == 6

    # check reauth trigger with bad-auth responses
    with freeze_time(_MOCK_TIME_BAD_AUTH_RESPONSES):
        await hass.async_block_till_done()
        assert pvpc_aioclient_mock.call_count == 10

        result = hass.config_entries.flow.async_progress_by_handler(DOMAIN)[0]
        assert result["context"]["entry_id"] == config_entry.entry_id
        assert result["context"]["source"] == SOURCE_REAUTH
        assert result["step_id"] == "reauth_confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=_BAD_TOKEN
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert pvpc_aioclient_mock.call_count == 11

    with freeze_time(_MOCK_TIME_VALID_RESPONSES):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=_GOOD_TOKEN
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
        assert pvpc_aioclient_mock.call_count == 12
