"""Tests for Vizio config flow."""
import logging

from asynctest import patch
import pytest
import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.media_player import DEVICE_CLASS_SPEAKER, DEVICE_CLASS_TV
from homeassistant.components.vizio.const import (
    CONF_VOLUME_STEP,
    DEFAULT_NAME,
    DEFAULT_VOLUME_STEP,
    DOMAIN,
    VIZIO_SCHEMA,
)
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_NAME,
)
from homeassistant.helpers.typing import HomeAssistantType

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)

NAME = "Vizio"
HOST = "192.168.1.1:9000"
ACCESS_TOKEN = "deadbeef"
VOLUME_STEP = 2
UNIQUE_ID = "testid"

MOCK_USER_VALID_TV_CONFIG = {
    CONF_NAME: NAME,
    CONF_HOST: HOST,
    CONF_DEVICE_CLASS: DEVICE_CLASS_TV,
    CONF_ACCESS_TOKEN: ACCESS_TOKEN,
}

MOCK_IMPORT_VALID_TV_CONFIG = {
    CONF_NAME: NAME,
    CONF_HOST: HOST,
    CONF_DEVICE_CLASS: DEVICE_CLASS_TV,
    CONF_ACCESS_TOKEN: ACCESS_TOKEN,
    CONF_VOLUME_STEP: VOLUME_STEP,
}

MOCK_INVALID_TV_CONFIG = {
    CONF_NAME: NAME,
    CONF_HOST: HOST,
    CONF_DEVICE_CLASS: DEVICE_CLASS_TV,
}

MOCK_SPEAKER_CONFIG = {
    CONF_NAME: NAME,
    CONF_HOST: HOST,
    CONF_DEVICE_CLASS: DEVICE_CLASS_SPEAKER,
}


@pytest.fixture(name="vizio_connect")
def vizio_connect_fixture():
    """Mock valid vizio device and entry setup."""
    with patch(
        "homeassistant.components.vizio.config_flow.VizioAsync.validate_ha_config",
        return_value=True,
    ), patch(
        "homeassistant.components.vizio.config_flow.VizioAsync.get_unique_id",
        return_value=UNIQUE_ID,
    ), patch(
        "homeassistant.components.vizio.async_setup_entry", return_value=True
    ):
        yield


@pytest.fixture(name="vizio_cant_connect")
def vizio_cant_connect_fixture():
    """Mock vizio device cant connect."""
    with patch(
        "homeassistant.components.vizio.config_flow.VizioAsync.validate_ha_config",
        return_value=False,
    ):
        yield


async def test_user_flow_minimum_fields(hass: HomeAssistantType, vizio_connect) -> None:
    """Test user config flow with minimum fields."""
    # test form shows
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_NAME: NAME,
            CONF_HOST: HOST,
            CONF_DEVICE_CLASS: DEVICE_CLASS_SPEAKER,
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"][CONF_NAME] == NAME
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_DEVICE_CLASS] == DEVICE_CLASS_SPEAKER


async def test_user_flow_all_fields(hass: HomeAssistantType, vizio_connect) -> None:
    """Test user config flow with all fields."""
    # test form shows
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_NAME: NAME,
            CONF_HOST: HOST,
            CONF_DEVICE_CLASS: DEVICE_CLASS_TV,
            CONF_ACCESS_TOKEN: ACCESS_TOKEN,
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"][CONF_NAME] == NAME
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_DEVICE_CLASS] == DEVICE_CLASS_TV
    assert result["data"][CONF_ACCESS_TOKEN] == ACCESS_TOKEN


async def test_options_flow(hass: HomeAssistantType) -> None:
    """Test options config flow."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_SPEAKER_CONFIG)
    entry.add_to_hass(hass)

    assert not entry.options

    result = await hass.config_entries.options.async_init(
        entry.entry_id, context={"source": "test"}, data=None
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_VOLUME_STEP: VOLUME_STEP},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == ""
    assert result["data"][CONF_VOLUME_STEP] == VOLUME_STEP


async def test_user_host_already_configured(
    hass: HomeAssistantType, vizio_connect
) -> None:
    """Test host is already configured during user setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_SPEAKER_CONFIG,
        options={CONF_VOLUME_STEP: VOLUME_STEP},
    )
    entry.add_to_hass(hass)
    fail_entry = MOCK_SPEAKER_CONFIG.copy()
    fail_entry[CONF_NAME] = "newtestname"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=fail_entry
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_HOST: "host_exists"}


async def test_user_name_already_configured(
    hass: HomeAssistantType, vizio_connect
) -> None:
    """Test name is already configured during user setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_SPEAKER_CONFIG,
        options={CONF_VOLUME_STEP: VOLUME_STEP},
    )
    entry.add_to_hass(hass)

    fail_entry = MOCK_SPEAKER_CONFIG.copy()
    fail_entry[CONF_HOST] = "0.0.0.0"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], fail_entry
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_NAME: "name_exists"}


async def test_user_error_on_could_not_connect(
    hass: HomeAssistantType, vizio_cant_connect
) -> None:
    """Test with could_not_connect during user_setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_USER_VALID_TV_CONFIG
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "cant_connect"}


async def test_user_error_on_tv_needs_token(
    hass: HomeAssistantType, vizio_connect
) -> None:
    """Test when config fails custom validation for non null access token when device_class = tv during user setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_INVALID_TV_CONFIG
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "tv_needs_token"}


async def test_import_flow_minimum_fields(
    hass: HomeAssistantType, vizio_connect
) -> None:
    """Test import config flow with minimum fields."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "import"},
        data=vol.Schema(VIZIO_SCHEMA)(
            {CONF_HOST: HOST, CONF_DEVICE_CLASS: DEVICE_CLASS_SPEAKER}
        ),
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"][CONF_NAME] == DEFAULT_NAME
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_DEVICE_CLASS] == DEVICE_CLASS_SPEAKER
    assert result["data"][CONF_VOLUME_STEP] == DEFAULT_VOLUME_STEP


async def test_import_flow_all_fields(hass: HomeAssistantType, vizio_connect) -> None:
    """Test import config flow with all fields."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "import"},
        data=vol.Schema(VIZIO_SCHEMA)(MOCK_IMPORT_VALID_TV_CONFIG),
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"][CONF_NAME] == NAME
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_DEVICE_CLASS] == DEVICE_CLASS_TV
    assert result["data"][CONF_ACCESS_TOKEN] == ACCESS_TOKEN
    assert result["data"][CONF_VOLUME_STEP] == VOLUME_STEP


async def test_import_entity_already_configured(
    hass: HomeAssistantType, vizio_connect
) -> None:
    """Test entity is already configured during import setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=vol.Schema(VIZIO_SCHEMA)(MOCK_SPEAKER_CONFIG),
        options={CONF_VOLUME_STEP: VOLUME_STEP},
    )
    entry.add_to_hass(hass)
    fail_entry = vol.Schema(VIZIO_SCHEMA)(MOCK_SPEAKER_CONFIG.copy())

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "import"}, data=fail_entry
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_setup"
