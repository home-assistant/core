"""Test the Google Cloud config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.google_cloud.const import CONF_KEY_FILE, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user_flow_success(
    hass: HomeAssistant,
    create_google_credentials_json: str,
) -> None:
    """Test user flow creates entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    with patch(
        "homeassistant.components.google_cloud.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_KEY_FILE: create_google_credentials_json,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Google Cloud"
    assert result["data"] == {
        CONF_KEY_FILE: create_google_credentials_json,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_file_not_found(
    hass: HomeAssistant,
) -> None:
    """Test user flow with file_not_found error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.google_cloud.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_KEY_FILE: "non_existent_file",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {
        "base": "file_not_found",
    }
    assert len(mock_setup_entry.mock_calls) == 0


async def test_reauth_flow(
    hass: HomeAssistant, create_google_credentials_json: str
) -> None:
    """Test the reauth flow."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_KEY_FILE: "some_invalid_file"},
        state=config_entries.ConfigEntryState.LOADED,
        title="my title",
    )
    mock_config_entry.add_to_hass(hass)
    hass.config.components.add(DOMAIN)
    mock_config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    result = flows[0]
    assert result["step_id"] == "reauth_confirm"
    assert result["context"]["source"] == "reauth"
    assert result["context"]["title_placeholders"] == {"name": "my title"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert CONF_KEY_FILE in result["data_schema"].schema
    assert not result["errors"]

    with (
        patch(
            "homeassistant.components.google_cloud.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
        patch(
            "homeassistant.components.google_cloud.async_unload_entry",
            return_value=True,
        ) as mock_unload_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_KEY_FILE: create_google_credentials_json}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert hass.config_entries.async_entries(DOMAIN)[0].data == {
        CONF_KEY_FILE: create_google_credentials_json
    }
    assert len(mock_unload_entry.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_options_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_tts,
) -> None:
    """Test options flow."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

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
        "stt_model": "command_and_search",
    }
    await hass.async_block_till_done()
