"""Test the ClimaCell config flow."""
from datetime import timedelta
import logging

from pyclimacell.exceptions import (
    CantConnectException,
    InvalidAPIKeyException,
    RateLimitedException,
    UnknownException,
)
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.air_quality import DOMAIN as AIR_QUALITY_DOMAIN
from homeassistant.components.climacell.config_flow import (
    _get_config_schema,
    _get_unique_id,
)
from homeassistant.components.climacell.const import (
    CONF_AQI_COUNTRY,
    CONF_FORECAST_TYPE,
    CONF_TIMESTEP,
    DAILY,
    DEFAULT_NAME,
    DOMAIN,
    NOWCAST,
)
from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.helpers.entity_registry import (
    async_entries_for_config_entry,
    async_get_registry,
)
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import dt

from .const import API_KEY, MIN_CONFIG

from tests.async_mock import patch
from tests.common import MockConfigEntry, async_fire_time_changed

_LOGGER = logging.getLogger(__name__)


async def test_user_flow_minimum_fields(hass: HomeAssistantType) -> None:
    """Test user config flow with minimum fields."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=_get_config_schema(hass, MIN_CONFIG)(MIN_CONFIG),
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"][CONF_NAME] == DEFAULT_NAME
    assert result["data"][CONF_API_KEY] == API_KEY
    assert result["data"][CONF_FORECAST_TYPE] == DAILY
    assert result["data"][CONF_LATITUDE] == hass.config.latitude
    assert result["data"][CONF_LONGITUDE] == hass.config.longitude


async def test_user_flow_same_unique_ids(hass: HomeAssistantType) -> None:
    """Test user config flow with the same unique ID as an existing entry."""
    user_input = _get_config_schema(hass, MIN_CONFIG)(MIN_CONFIG)
    MockConfigEntry(
        domain=DOMAIN,
        data=user_input,
        source=SOURCE_USER,
        unique_id=_get_unique_id(hass, user_input),
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=user_input,
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_cannot_connect(hass: HomeAssistantType) -> None:
    """Test user config flow when ClimaCell can't connect."""
    with patch(
        "homeassistant.components.climacell.config_flow.ClimaCell.realtime",
        side_effect=CantConnectException,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=_get_config_schema(hass, MIN_CONFIG)(MIN_CONFIG),
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_invalid_api(hass: HomeAssistantType) -> None:
    """Test user config flow when API key is invalid."""
    with patch(
        "homeassistant.components.climacell.config_flow.ClimaCell.realtime",
        side_effect=InvalidAPIKeyException,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=_get_config_schema(hass, MIN_CONFIG)(MIN_CONFIG),
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {CONF_API_KEY: "invalid_api_key"}


async def test_user_flow_rate_limited(hass: HomeAssistantType) -> None:
    """Test user config flow when API key is rate limited."""
    with patch(
        "homeassistant.components.climacell.config_flow.ClimaCell.realtime",
        side_effect=RateLimitedException,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=_get_config_schema(hass, MIN_CONFIG)(MIN_CONFIG),
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {CONF_API_KEY: "rate_limited"}


async def test_user_flow_unknown_exception(hass: HomeAssistantType) -> None:
    """Test user config flow when unknown error occurs."""
    with patch(
        "homeassistant.components.climacell.config_flow.ClimaCell.realtime",
        side_effect=UnknownException,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=_get_config_schema(hass, MIN_CONFIG)(MIN_CONFIG),
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "unknown"}


async def test_options_flow(hass: HomeAssistantType) -> None:
    """Test options config flow for climacell."""
    user_config = _get_config_schema(hass)(MIN_CONFIG)
    user_config[CONF_FORECAST_TYPE] = NOWCAST
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=user_config,
        source=SOURCE_USER,
        unique_id=_get_unique_id(hass, user_config),
    )
    entry.add_to_hass(hass)

    assert not entry.options
    assert CONF_TIMESTEP not in entry.data
    assert CONF_AQI_COUNTRY not in entry.data

    result = await hass.config_entries.options.async_init(entry.entry_id, data=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    assert CONF_AQI_COUNTRY not in result["data_schema"].schema

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_TIMESTEP: 1}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == ""
    assert result["data"][CONF_TIMESTEP] == 1
    assert entry.options[CONF_TIMESTEP] == 1


async def test_options_flow_after_enabling_aq_entity(
    hass: HomeAssistantType, climacell_config_entry_update: pytest.fixture
) -> None:
    """Test options flow includes `aqi_country` after enabling air_quality entity."""
    user_config = _get_config_schema(hass)(MIN_CONFIG)
    user_config[CONF_FORECAST_TYPE] = NOWCAST
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=user_config,
        source=SOURCE_USER,
        unique_id=_get_unique_id(hass, user_config),
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(WEATHER_DOMAIN)) == 1
    assert len(hass.states.async_entity_ids(AIR_QUALITY_DOMAIN)) == 0

    entity_registry = await async_get_registry(hass)
    for entity in async_entries_for_config_entry(entity_registry, entry.entry_id):
        if entity.domain == AIR_QUALITY_DOMAIN:
            entity_registry.async_update_entity(entity.entity_id, disabled_by=None)
            # Force reload of entry to finish enabling entity
            await hass.config_entries.async_reload(entry.entry_id)
            async_fire_time_changed(hass, dt.now() + timedelta(hours=1))
            await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(AIR_QUALITY_DOMAIN)) == 1

    result = await hass.config_entries.options.async_init(entry.entry_id, data=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    assert CONF_AQI_COUNTRY in result["data_schema"].schema

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_TIMESTEP: 1, CONF_AQI_COUNTRY: "china"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == ""
    assert result["data"][CONF_TIMESTEP] == 1
    assert entry.options[CONF_TIMESTEP] == 1
    assert result["data"][CONF_AQI_COUNTRY] == "china"
    assert entry.options[CONF_AQI_COUNTRY] == "china"
