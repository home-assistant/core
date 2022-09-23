"""Test the Tomorrow.io config flow."""
from unittest.mock import patch

from pytomorrowio.exceptions import (
    CantConnectException,
    InvalidAPIKeyException,
    RateLimitedException,
    UnknownException,
)

from homeassistant import data_entry_flow
from homeassistant.components.tomorrowio.config_flow import (
    _get_config_schema,
    _get_unique_id,
)
from homeassistant.components.tomorrowio.const import (
    CONF_TIMESTEP,
    DEFAULT_NAME,
    DEFAULT_TIMESTEP,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_RADIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import API_KEY, MIN_CONFIG

from tests.common import MockConfigEntry


async def test_user_flow_minimum_fields(hass: HomeAssistant) -> None:
    """Test user config flow with minimum fields."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=_get_config_schema(hass, SOURCE_USER, MIN_CONFIG)(MIN_CONFIG),
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"][CONF_NAME] == DEFAULT_NAME
    assert result["data"][CONF_API_KEY] == API_KEY
    assert result["data"][CONF_LOCATION][CONF_LATITUDE] == hass.config.latitude
    assert result["data"][CONF_LOCATION][CONF_LONGITUDE] == hass.config.longitude


async def test_user_flow_minimum_fields_in_zone(hass: HomeAssistant) -> None:
    """Test user config flow with minimum fields."""
    assert await async_setup_component(
        hass,
        "zone",
        {
            "zone": {
                CONF_NAME: "Home",
                CONF_LATITUDE: hass.config.latitude,
                CONF_LONGITUDE: hass.config.longitude,
                CONF_RADIUS: 100,
            }
        },
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=_get_config_schema(hass, SOURCE_USER, MIN_CONFIG)(MIN_CONFIG),
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == f"{DEFAULT_NAME} - Home"
    assert result["data"][CONF_NAME] == f"{DEFAULT_NAME} - Home"
    assert result["data"][CONF_API_KEY] == API_KEY
    assert result["data"][CONF_LOCATION][CONF_LATITUDE] == hass.config.latitude
    assert result["data"][CONF_LOCATION][CONF_LONGITUDE] == hass.config.longitude


async def test_user_flow_same_unique_ids(hass: HomeAssistant) -> None:
    """Test user config flow with the same unique ID as an existing entry."""
    user_input = _get_config_schema(hass, SOURCE_USER, MIN_CONFIG)(MIN_CONFIG)
    MockConfigEntry(
        domain=DOMAIN,
        data=user_input,
        options={CONF_TIMESTEP: DEFAULT_TIMESTEP},
        source=SOURCE_USER,
        unique_id=_get_unique_id(hass, user_input),
        version=2,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=user_input,
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test user config flow when Tomorrow.io can't connect."""
    with patch(
        "homeassistant.components.tomorrowio.config_flow.TomorrowioV4.realtime",
        side_effect=CantConnectException,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=_get_config_schema(hass, SOURCE_USER, MIN_CONFIG)(MIN_CONFIG),
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_invalid_api(hass: HomeAssistant) -> None:
    """Test user config flow when API key is invalid."""
    with patch(
        "homeassistant.components.tomorrowio.config_flow.TomorrowioV4.realtime",
        side_effect=InvalidAPIKeyException,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=_get_config_schema(hass, SOURCE_USER, MIN_CONFIG)(MIN_CONFIG),
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == {CONF_API_KEY: "invalid_api_key"}


async def test_user_flow_rate_limited(hass: HomeAssistant) -> None:
    """Test user config flow when API key is rate limited."""
    with patch(
        "homeassistant.components.tomorrowio.config_flow.TomorrowioV4.realtime",
        side_effect=RateLimitedException,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=_get_config_schema(hass, SOURCE_USER, MIN_CONFIG)(MIN_CONFIG),
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == {CONF_API_KEY: "rate_limited"}


async def test_user_flow_unknown_exception(hass: HomeAssistant) -> None:
    """Test user config flow when unknown error occurs."""
    with patch(
        "homeassistant.components.tomorrowio.config_flow.TomorrowioV4.realtime",
        side_effect=UnknownException,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=_get_config_schema(hass, SOURCE_USER, MIN_CONFIG)(MIN_CONFIG),
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test options config flow for tomorrowio."""
    user_config = _get_config_schema(hass, SOURCE_USER)(MIN_CONFIG)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=user_config,
        options={CONF_TIMESTEP: DEFAULT_TIMESTEP},
        source=SOURCE_USER,
        unique_id=_get_unique_id(hass, user_config),
        version=1,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.options[CONF_TIMESTEP] == DEFAULT_TIMESTEP
    assert CONF_TIMESTEP not in entry.data

    result = await hass.config_entries.options.async_init(entry.entry_id, data=None)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_TIMESTEP: 1}
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == ""
    assert result["data"][CONF_TIMESTEP] == 1
    assert entry.options[CONF_TIMESTEP] == 1
