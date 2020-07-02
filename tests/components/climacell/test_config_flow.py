"""Test the ClimaCell config flow."""
import logging

from pyclimacell.exceptions import (
    CantConnectException,
    InvalidAPIKeyException,
    RateLimitedException,
    UnknownException,
)

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.climacell import SCHEMA
from homeassistant.components.climacell.config_flow import (
    _get_config_schema,
    _get_unique_id,
)
from homeassistant.components.climacell.const import (
    CONF_AQI_COUNTRY,
    CONF_FORECAST_TYPE,
    CONF_TIMESTEP,
    DAILY,
    DEFAULT_AQI_COUNTRY,
    DEFAULT_NAME,
    DEFAULT_TIMESTEP,
    DOMAIN,
    NOWCAST,
    USA,
)
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.helpers.typing import HomeAssistantType

from .const import API_KEY, MIN_CONFIG

from tests.async_mock import patch
from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


async def test_user_flow_minimum_fields(hass: HomeAssistantType) -> None:
    """Test user config flow with minimum fields."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
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
        source=config_entries.SOURCE_USER,
        unique_id=_get_unique_id(hass, user_input),
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=user_input,
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
            context={"source": config_entries.SOURCE_USER},
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
            context={"source": config_entries.SOURCE_USER},
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
            context={"source": config_entries.SOURCE_USER},
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
            context={"source": config_entries.SOURCE_USER},
            data=_get_config_schema(hass, MIN_CONFIG)(MIN_CONFIG),
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "unknown"}


async def test_import_flow_minimum_fields(hass: HomeAssistantType) -> None:
    """Test import config flow with minimum fields."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=SCHEMA(MIN_CONFIG),
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"][CONF_NAME] == DEFAULT_NAME
    assert result["data"][CONF_API_KEY] == API_KEY
    assert result["data"][CONF_FORECAST_TYPE] == DAILY
    assert CONF_LATITUDE not in result["data"]
    assert CONF_LONGITUDE not in result["data"]
    assert result["data"][CONF_AQI_COUNTRY] == USA


async def test_import_flow_already_exists(hass: HomeAssistantType) -> None:
    """Test import config flow when entry already exists."""
    import_config = SCHEMA(MIN_CONFIG)
    MockConfigEntry(
        domain=DOMAIN,
        data=import_config,
        source=config_entries.SOURCE_IMPORT,
        unique_id=_get_unique_id(hass, import_config),
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=import_config,
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured_account"


async def test_import_flow_update_entry(hass: HomeAssistantType) -> None:
    """Test import config flow when config is updated."""
    import_config = SCHEMA(MIN_CONFIG)
    MockConfigEntry(
        domain=DOMAIN,
        data=import_config,
        source=config_entries.SOURCE_IMPORT,
        unique_id=_get_unique_id(hass, import_config),
    ).add_to_hass(hass)

    config = MIN_CONFIG.copy()
    config[CONF_NAME] = "test name"
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=SCHEMA(config),
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "updated_entry"


async def test_import_flow_update_timestep(hass: HomeAssistantType) -> None:
    """Test import config flow when timestep is updated."""
    import_config = SCHEMA(MIN_CONFIG)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=import_config,
        source=config_entries.SOURCE_IMPORT,
        unique_id=_get_unique_id(hass, import_config),
    )
    entry.add_to_hass(hass)

    config = MIN_CONFIG.copy()
    config[CONF_TIMESTEP] = 1
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=SCHEMA(config),
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "updated_entry"
    assert entry.data[CONF_TIMESTEP] == entry.options[CONF_TIMESTEP] == 1


async def test_import_flow_update_aqi_country(hass: HomeAssistantType) -> None:
    """Test import config flow when aqi_country is updated."""
    import_config = SCHEMA(MIN_CONFIG)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=import_config,
        source=config_entries.SOURCE_IMPORT,
        unique_id=_get_unique_id(hass, import_config),
    )
    entry.add_to_hass(hass)

    config = MIN_CONFIG.copy()
    config[CONF_AQI_COUNTRY] = "china"
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=SCHEMA(config),
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "updated_entry"
    assert entry.data[CONF_AQI_COUNTRY] == entry.options[CONF_AQI_COUNTRY] == "china"


async def test_options_flow(hass: HomeAssistantType) -> None:
    """Test options config flow for climacell."""
    import_config = SCHEMA(MIN_CONFIG)
    import_config[CONF_FORECAST_TYPE] = NOWCAST
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=import_config,
        source=config_entries.SOURCE_IMPORT,
        unique_id=_get_unique_id(hass, import_config),
    )
    entry.add_to_hass(hass)

    assert not entry.options
    assert entry.data[CONF_TIMESTEP] == DEFAULT_TIMESTEP
    assert entry.data[CONF_AQI_COUNTRY] == DEFAULT_AQI_COUNTRY

    result = await hass.config_entries.options.async_init(entry.entry_id, data=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_TIMESTEP: 1, CONF_AQI_COUNTRY: "china"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == ""
    assert result["data"][CONF_TIMESTEP] == 1
    assert entry.options[CONF_TIMESTEP] == 1
    assert result["data"][CONF_AQI_COUNTRY] == "china"
    assert entry.options[CONF_AQI_COUNTRY] == "china"
