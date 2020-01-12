"""Tests for Vizio config flow."""
import logging

from asynctest import patch
import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.vizio import VIZIO_SCHEMA
from homeassistant.components.vizio.const import (
    CONF_VOLUME_STEP,
    DEFAULT_NAME,
    DEFAULT_VOLUME_STEP,
    DOMAIN,
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
NAME2 = "Vizio2"
HOST = "192.168.1.1:9000"
HOST2 = "192.168.1.2:9000"
DEVICE_CLASS_TV = "tv"
DEVICE_CLASS_SOUNDBAR = "soundbar"
ACCESS_TOKEN = "deadbeef"
VOLUME_STEP = 2

MOCK_USER_VALID_TV_ENTRY = {
    CONF_NAME: NAME2,
    CONF_HOST: HOST2,
    CONF_DEVICE_CLASS: DEVICE_CLASS_TV,
    CONF_ACCESS_TOKEN: ACCESS_TOKEN,
}

MOCK_IMPORT_VALID_TV_ENTRY = {
    CONF_NAME: NAME2,
    CONF_HOST: HOST2,
    CONF_DEVICE_CLASS: DEVICE_CLASS_TV,
    CONF_ACCESS_TOKEN: ACCESS_TOKEN,
    CONF_VOLUME_STEP: VOLUME_STEP,
}

MOCK_INVALID_TV_ENTRY = {
    CONF_NAME: NAME,
    CONF_HOST: HOST,
    CONF_DEVICE_CLASS: DEVICE_CLASS_TV,
}

MOCK_SOUNDBAR_ENTRY = {
    CONF_NAME: NAME,
    CONF_HOST: HOST,
    CONF_DEVICE_CLASS: DEVICE_CLASS_SOUNDBAR,
}


async def test_flow_works(hass: HomeAssistantType) -> None:
    """Test user config."""

    # test form shows
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    # test valid options
    with patch("pyvizio.VizioAsync.validate_ha_config", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_NAME: NAME,
                CONF_HOST: HOST,
                CONF_DEVICE_CLASS: DEVICE_CLASS_SOUNDBAR,
                CONF_VOLUME_STEP: DEFAULT_VOLUME_STEP,
            },
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"][CONF_NAME] == NAME
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_DEVICE_CLASS] == DEVICE_CLASS_SOUNDBAR
    assert result["data"][CONF_VOLUME_STEP] == DEFAULT_VOLUME_STEP
    await hass.config_entries.async_unload(result["result"].entry_id)

    # test with all provided
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch("pyvizio.VizioAsync.validate_ha_config", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_NAME: NAME2,
                CONF_HOST: HOST2,
                CONF_DEVICE_CLASS: DEVICE_CLASS_TV,
                CONF_ACCESS_TOKEN: ACCESS_TOKEN,
                CONF_VOLUME_STEP: VOLUME_STEP,
            },
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == NAME2
    assert result["data"][CONF_NAME] == NAME2
    assert result["data"][CONF_HOST] == HOST2
    assert result["data"][CONF_DEVICE_CLASS] == DEVICE_CLASS_TV
    assert result["data"][CONF_ACCESS_TOKEN] == ACCESS_TOKEN
    assert result["data"][CONF_VOLUME_STEP] == VOLUME_STEP


async def test_user_host_already_configured(hass: HomeAssistantType) -> None:
    """Test host is already configured during user setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_SOUNDBAR_ENTRY,
        options={CONF_VOLUME_STEP: VOLUME_STEP},
    )
    entry.add_to_hass(hass)
    fail_entry = MOCK_SOUNDBAR_ENTRY.copy()
    fail_entry[CONF_NAME] = "newtestname"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch("pyvizio.VizioAsync.validate_ha_config", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=fail_entry,
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_HOST: "host_exists"}


async def test_user_name_already_configured(hass: HomeAssistantType) -> None:
    """Test name is already configured during user setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_SOUNDBAR_ENTRY,
        options={CONF_VOLUME_STEP: VOLUME_STEP},
    )
    entry.add_to_hass(hass)

    fail_entry = MOCK_SOUNDBAR_ENTRY.copy()
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


async def test_user_error_on_could_not_connect(hass: HomeAssistantType) -> None:
    """Test with could_not_connect during user_setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch("pyvizio.VizioAsync.validate_ha_config", return_value=False):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_USER_VALID_TV_ENTRY
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "no_connect"}


async def test_user_error_on_tv_needs_token(hass: HomeAssistantType) -> None:
    """Test when config fails custom validation for non null access token when device_class = tv during user setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], MOCK_INVALID_TV_ENTRY
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "tv_needs_token"}


async def test_import(hass: HomeAssistantType) -> None:
    """Test import step."""
    # import with minimum fields only
    with patch("pyvizio.VizioAsync.validate_ha_config", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "import"},
            data=vol.Schema(VIZIO_SCHEMA)(
                {CONF_HOST: HOST, CONF_DEVICE_CLASS: DEVICE_CLASS_SOUNDBAR}
            ),
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"][CONF_NAME] == DEFAULT_NAME
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_DEVICE_CLASS] == DEVICE_CLASS_SOUNDBAR
    assert result["data"][CONF_VOLUME_STEP] == DEFAULT_VOLUME_STEP

    # import with all
    with patch("pyvizio.VizioAsync.validate_ha_config", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "import"},
            data=vol.Schema(VIZIO_SCHEMA)(MOCK_IMPORT_VALID_TV_ENTRY),
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == NAME2
    assert result["data"][CONF_NAME] == NAME2
    assert result["data"][CONF_HOST] == HOST2
    assert result["data"][CONF_DEVICE_CLASS] == DEVICE_CLASS_TV
    assert result["data"][CONF_ACCESS_TOKEN] == ACCESS_TOKEN
    assert result["data"][CONF_VOLUME_STEP] == VOLUME_STEP


async def test_import_entity_already_configured(hass: HomeAssistantType) -> None:
    """Test entity is already configured during import setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_SOUNDBAR_ENTRY,
        options={CONF_VOLUME_STEP: VOLUME_STEP},
    )
    entry.add_to_hass(hass)
    fail_entry = MOCK_SOUNDBAR_ENTRY.copy()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "import"}, data=fail_entry
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_setup"
