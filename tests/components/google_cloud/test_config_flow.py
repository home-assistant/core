"""Test the Google Cloud config flow."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from homeassistant import config_entries
from homeassistant.components import tts
from homeassistant.components.google_cloud.config_flow import UPLOADED_KEY_FILE
from homeassistant.components.google_cloud.const import (
    CONF_KEY_FILE,
    CONF_SERVICE_ACCOUNT_INFO,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from .conftest import VALID_SERVICE_ACCOUNT_INFO

from tests.common import MockConfigEntry


async def test_user_flow_success(
    hass: HomeAssistant,
    mock_process_uploaded_file: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test user flow creates entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    uploaded_file = str(uuid4())
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {UPLOADED_KEY_FILE: uploaded_file},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Google Cloud"
    assert result["data"] == {CONF_SERVICE_ACCOUNT_INFO: VALID_SERVICE_ACCOUNT_INFO}
    mock_process_uploaded_file.assert_called_with(hass, uploaded_file)
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_missing_file(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test user flow when uploaded file is missing."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {UPLOADED_KEY_FILE: str(uuid4())},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_file"}
    assert len(mock_setup_entry.mock_calls) == 0


async def test_user_flow_invalid_file(
    hass: HomeAssistant,
    create_invalid_google_credentials_json: str,
    mock_process_uploaded_file: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test user flow when uploaded file is invalid."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    uploaded_file = str(uuid4())
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {UPLOADED_KEY_FILE: uploaded_file},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_file"}
    mock_process_uploaded_file.assert_called_with(hass, uploaded_file)
    assert len(mock_setup_entry.mock_calls) == 0


async def test_import_flow(
    hass: HomeAssistant,
    create_google_credentials_json: str,
    mock_api_tts_from_service_account_file: AsyncMock,
    mock_api_tts_from_service_account_info: AsyncMock,
) -> None:
    """Test the import flow."""
    assert not hass.config_entries.async_entries(DOMAIN)
    assert await async_setup_component(
        hass,
        tts.DOMAIN,
        {
            tts.DOMAIN: {CONF_PLATFORM: DOMAIN}
            | {CONF_KEY_FILE: create_google_credentials_json}
        },
    )
    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.state is config_entries.ConfigEntryState.LOADED


async def test_import_flow_invalid_file(
    hass: HomeAssistant,
    create_invalid_google_credentials_json: str,
    mock_api_tts_from_service_account_file: AsyncMock,
) -> None:
    """Test the import flow when the key file is invalid."""
    assert not hass.config_entries.async_entries(DOMAIN)
    assert await async_setup_component(
        hass,
        tts.DOMAIN,
        {
            tts.DOMAIN: {CONF_PLATFORM: DOMAIN}
            | {CONF_KEY_FILE: create_invalid_google_credentials_json}
        },
    )
    await hass.async_block_till_done()
    assert not hass.config_entries.async_entries(DOMAIN)
    assert mock_api_tts_from_service_account_file.list_voices.call_count == 1


async def test_options_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_tts_from_service_account_info: AsyncMock,
) -> None:
    """Test options flow."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_api_tts_from_service_account_info.list_voices.call_count == 1

    assert mock_config_entry.options == {}

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    data_schema = result["data_schema"].schema
    assert set(data_schema) == {
        "language",
        "gender",
        "voice",
        "encoding",
        "speed",
        "pitch",
        "gain",
        "profiles",
        "text_type",
        "stt_model",
    }
    assert mock_api_tts_from_service_account_info.list_voices.call_count == 2

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"language": "el-GR"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {
        "language": "el-GR",
        "gender": "NEUTRAL",
        "voice": "",
        "encoding": "MP3",
        "speed": 1.0,
        "pitch": 0.0,
        "gain": 0.0,
        "profiles": [],
        "text_type": "text",
        "stt_model": "latest_short",
    }
    assert mock_api_tts_from_service_account_info.list_voices.call_count == 3
