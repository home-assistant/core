"""Test the Tomorrow.io config flow."""

from unittest.mock import patch

import pytest
from pytomorrowio.exceptions import (
    CantConnectException,
    InvalidAPIKeyException,
    RateLimitedException,
    UnknownException,
)

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
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from .const import API_KEY, MIN_CONFIG

from tests.common import MockConfigEntry


async def test_user_flow_minimum_fields(hass: HomeAssistant) -> None:
    """Test user config flow with minimum fields."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=_get_config_schema(hass, SOURCE_USER, MIN_CONFIG)(MIN_CONFIG),
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
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
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=_get_config_schema(hass, SOURCE_USER, MIN_CONFIG)(MIN_CONFIG),
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
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
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=user_input,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "errors"),
    [
        (CantConnectException, {"base": "cannot_connect"}),
        (InvalidAPIKeyException, {CONF_API_KEY: "invalid_api_key"}),
        (RateLimitedException, {CONF_API_KEY: "rate_limited"}),
        (UnknownException, {"base": "unknown"}),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant, side_effect: type[Exception], errors: dict[str, str]
) -> None:
    """Test user config flow errors and recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.tomorrowio.config_flow.TomorrowioV4.realtime",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=_get_config_schema(hass, SOURCE_USER, MIN_CONFIG)(MIN_CONFIG),
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=_get_config_schema(hass, SOURCE_USER, MIN_CONFIG)(MIN_CONFIG),
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {
        CONF_NAME: DEFAULT_NAME,
        CONF_API_KEY: API_KEY,
        CONF_LOCATION: {
            CONF_LATITUDE: hass.config.latitude,
            CONF_LONGITUDE: hass.config.longitude,
        },
    }


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

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_TIMESTEP: 1}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ""
    assert result["data"][CONF_TIMESTEP] == 1
    assert entry.options[CONF_TIMESTEP] == 1
