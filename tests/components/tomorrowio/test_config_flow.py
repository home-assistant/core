"""Test the Tomorrow.io config flow."""
import logging
from unittest.mock import patch

import pytest
from pytomorrowio.exceptions import (
    CantConnectException,
    InvalidAPIKeyException,
    RateLimitedException,
    UnknownException,
)

from homeassistant import data_entry_flow
from homeassistant.components.climacell.config_flow import (
    _get_config_schema as _get_climacell_config_schema,
    _get_unique_id as _get_climacell_unique_id,
)
from homeassistant.components.climacell.const import DOMAIN as CC_DOMAIN
from homeassistant.components.tomorrowio.config_flow import (
    _get_config_schema as _get_tomorrowio_config_schema,
    _get_unique_id as _get_tomorrowio_unique_id,
)
from homeassistant.components.tomorrowio.const import (
    CONF_TIMESTEP,
    DEFAULT_NAME,
    DEFAULT_TIMESTEP,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER, ConfigEntryState
from homeassistant.const import (
    CONF_API_KEY,
    CONF_API_VERSION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant

from .const import API_KEY, MIN_CONFIG

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


async def test_user_flow_minimum_fields(hass: HomeAssistant) -> None:
    """Test user config flow with minimum fields."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=_get_tomorrowio_config_schema(hass, SOURCE_USER, MIN_CONFIG)(
            MIN_CONFIG
        ),
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"][CONF_NAME] == DEFAULT_NAME
    assert result["data"][CONF_API_KEY] == API_KEY
    assert result["data"][CONF_LATITUDE] == hass.config.latitude
    assert result["data"][CONF_LONGITUDE] == hass.config.longitude


async def test_user_flow_same_unique_ids(hass: HomeAssistant) -> None:
    """Test user config flow with the same unique ID as an existing entry."""
    user_input = _get_tomorrowio_config_schema(hass, SOURCE_USER, MIN_CONFIG)(
        MIN_CONFIG
    )
    MockConfigEntry(
        domain=DOMAIN,
        data=user_input,
        source=SOURCE_USER,
        unique_id=_get_tomorrowio_unique_id(hass, user_input),
        version=2,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=user_input,
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
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
            data=_get_tomorrowio_config_schema(hass, SOURCE_USER, MIN_CONFIG)(
                MIN_CONFIG
            ),
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
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
            data=_get_tomorrowio_config_schema(hass, SOURCE_USER, MIN_CONFIG)(
                MIN_CONFIG
            ),
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
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
            data=_get_tomorrowio_config_schema(hass, SOURCE_USER, MIN_CONFIG)(
                MIN_CONFIG
            ),
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
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
            data=_get_tomorrowio_config_schema(hass, SOURCE_USER, MIN_CONFIG)(
                MIN_CONFIG
            ),
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "unknown"}


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test options config flow for tomorrowio."""
    user_config = _get_tomorrowio_config_schema(hass, SOURCE_USER)(MIN_CONFIG)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=user_config,
        source=SOURCE_USER,
        unique_id=_get_tomorrowio_unique_id(hass, user_config),
        version=1,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.options[CONF_TIMESTEP] == DEFAULT_TIMESTEP
    assert CONF_TIMESTEP not in entry.data

    result = await hass.config_entries.options.async_init(entry.entry_id, data=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_TIMESTEP: 1}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == ""
    assert result["data"][CONF_TIMESTEP] == 1
    assert entry.options[CONF_TIMESTEP] == 1


async def test_import_flow_v4(hass: HomeAssistant) -> None:
    """Test import flow for climacell v4 config entry."""
    user_config = _get_climacell_config_schema(hass)(MIN_CONFIG)
    old_entry = MockConfigEntry(
        domain=CC_DOMAIN,
        data=user_config,
        source=SOURCE_USER,
        unique_id=_get_climacell_unique_id(hass, user_config),
        version=1,
    )
    old_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT, "old_config_entry_id": old_entry.entry_id},
        data=old_entry.data,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        CONF_API_KEY: API_KEY,
        CONF_LATITUDE: hass.config.latitude,
        CONF_LONGITUDE: hass.config.longitude,
        CONF_NAME: "ClimaCell",
        "old_config_entry_id": old_entry.entry_id,
    }

    assert len(hass.config_entries.async_entries(CC_DOMAIN)) == 0
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert "old_config_entry_id" not in entry.data
    assert CONF_API_VERSION not in entry.data


async def test_import_flow_v3(
    hass: HomeAssistant,
    tomorrowio_config_entry_update: pytest.fixture,
    climacell_config_entry_update: pytest.fixture,
) -> None:
    """Test import flow for climacell v3 config entry."""
    user_config = _get_climacell_config_schema(hass)(MIN_CONFIG)
    user_config[CONF_API_VERSION] = 3
    old_entry = MockConfigEntry(
        domain=CC_DOMAIN,
        data=user_config,
        source=SOURCE_USER,
        unique_id=_get_climacell_unique_id(hass, user_config),
        version=1,
    )
    old_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(old_entry.entry_id)
    assert old_entry.state == ConfigEntryState.LOADED
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT, "old_config_entry_id": old_entry.entry_id},
        data=old_entry.data,
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "upgrade_needed"

    # Fake hitting submit on upgrade needed form
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "this is a test"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        CONF_API_KEY: "this is a test",
        CONF_LATITUDE: hass.config.latitude,
        CONF_LONGITUDE: hass.config.longitude,
        CONF_NAME: "ClimaCell",
        "old_config_entry_id": old_entry.entry_id,
    }

    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(CC_DOMAIN)) == 0
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert "old_config_entry_id" not in entry.data
    assert CONF_API_VERSION not in entry.data
