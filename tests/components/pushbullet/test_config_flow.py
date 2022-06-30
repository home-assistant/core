"""Test pushbullet config flow."""
from unittest.mock import MagicMock, patch

from pushbullet import InvalidKeyError
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.pushbullet.const import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from . import MOCK_CONFIG

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def pushbullet_setup_fixture():
    """Patch pushbullet setup entry."""
    with patch(
        "homeassistant.components.pushbullet.async_setup_entry", return_value=True
    ):
        yield


async def test_flow_user(hass: HomeAssistant) -> None:
    """Test user initialized flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "pushbullet"
    assert result["data"] == MOCK_CONFIG


async def test_flow_api_key_already_configured(hass: HomeAssistant) -> None:
    """Test user initialized flow with duplicate server."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        unique_id="MYAPIKEY",
    )

    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_flow_name_already_configured(hass: HomeAssistant) -> None:
    """Test user initialized flow with duplicate server."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        unique_id="MYAPIKEY",
    )

    entry.add_to_hass(hass)

    new_config = MOCK_CONFIG.copy()
    new_config[CONF_API_KEY] = "NEWKEY"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=new_config,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_flow_invalid_key(
    hass: HomeAssistant, mock_pushbullet: MagicMock
) -> None:
    """Test user initialized flow with unreachable server."""

    mock_pushbullet.side_effect = InvalidKeyError
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=MOCK_CONFIG,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_API_KEY: "invalid_api_key"}


async def test_import(hass: HomeAssistant) -> None:
    """Test user initialized flow with unreachable server."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=MOCK_CONFIG,
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "pushbullet"
    assert result["data"] == MOCK_CONFIG
