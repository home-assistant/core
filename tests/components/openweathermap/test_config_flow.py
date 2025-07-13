"""Define tests for the OpenWeatherMap config flow."""

from unittest.mock import AsyncMock

from pyopenweathermap import RequestError
import pytest

from homeassistant.components.openweathermap.const import (
    DEFAULT_LANGUAGE,
    DEFAULT_OWM_MODE,
    DOMAIN,
    OWM_MODE_V30,
)
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LANGUAGE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import LATITUDE, LONGITUDE

from tests.common import MockConfigEntry

CONFIG = {
    CONF_NAME: "openweathermap",
    CONF_API_KEY: "foo",
    CONF_LATITUDE: LATITUDE,
    CONF_LONGITUDE: LONGITUDE,
    CONF_LANGUAGE: DEFAULT_LANGUAGE,
    CONF_MODE: OWM_MODE_V30,
}

VALID_YAML_CONFIG = {CONF_API_KEY: "foo"}


async def test_successful_config_flow(
    hass: HomeAssistant,
    owm_client_mock: AsyncMock,
) -> None:
    """Test that the form is served with valid input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
    )

    await hass.async_block_till_done()

    conf_entries = hass.config_entries.async_entries(DOMAIN)
    entry = conf_entries[0]
    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(conf_entries[0].entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == CONFIG[CONF_NAME]
    assert result["data"][CONF_LATITUDE] == CONFIG[CONF_LATITUDE]
    assert result["data"][CONF_LONGITUDE] == CONFIG[CONF_LONGITUDE]
    assert result["data"][CONF_API_KEY] == CONFIG[CONF_API_KEY]


@pytest.mark.parametrize("mode", [OWM_MODE_V30], indirect=True)
async def test_abort_config_flow(
    hass: HomeAssistant,
    owm_client_mock: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the form is served with same data."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], CONFIG)

    assert result["type"] is FlowResultType.ABORT


async def test_config_flow_options_change(
    hass: HomeAssistant,
    owm_client_mock: AsyncMock,
) -> None:
    """Test that the options form."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="openweathermap_unique_id", data=CONFIG
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    new_language = "es"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_MODE: DEFAULT_OWM_MODE, CONF_LANGUAGE: new_language},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        CONF_LANGUAGE: new_language,
        CONF_MODE: DEFAULT_OWM_MODE,
    }

    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    updated_language = "es"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_LANGUAGE: updated_language}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        CONF_LANGUAGE: updated_language,
        CONF_MODE: DEFAULT_OWM_MODE,
    }

    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED


async def test_form_invalid_api_key(
    hass: HomeAssistant,
    owm_client_mock: AsyncMock,
) -> None:
    """Test that the form is served with no input."""
    owm_client_mock.validate_key.return_value = False
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_api_key"}

    owm_client_mock.validate_key.return_value = True
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_api_call_error(
    hass: HomeAssistant,
    owm_client_mock: AsyncMock,
) -> None:
    """Test setting up with api call error."""
    owm_client_mock.validate_key.side_effect = RequestError("oops")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    owm_client_mock.validate_key.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
