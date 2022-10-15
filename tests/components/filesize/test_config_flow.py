"""Tests for the Filesize config flow."""
from unittest.mock import patch

from homeassistant.components.filesize.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_FILE_PATH
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import TEST_DIR, TEST_FILE, TEST_FILE_NAME, async_create_file

from tests.common import MockConfigEntry


async def test_full_user_flow(hass: HomeAssistant) -> None:
    """Test the full user configuration flow."""
    await async_create_file(hass, TEST_FILE)
    hass.config.allowlist_external_dirs = {TEST_DIR}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == SOURCE_USER
    assert "flow_id" in result

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_FILE_PATH: TEST_FILE},
    )

    assert result2.get("type") == FlowResultType.CREATE_ENTRY
    assert result2.get("title") == TEST_FILE_NAME
    assert result2.get("data") == {CONF_FILE_PATH: TEST_FILE}


async def test_unique_path(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort if already setup."""
    await async_create_file(hass, TEST_FILE)
    hass.config.allowlist_external_dirs = {TEST_DIR}
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={CONF_FILE_PATH: TEST_FILE}
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_flow_fails_on_validation(hass: HomeAssistant) -> None:
    """Test config flow errors."""

    hass.config.allowlist_external_dirs = {}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_FILE_PATH: TEST_FILE,
        },
    )

    assert result2["errors"] == {"base": "not_valid"}

    await async_create_file(hass, TEST_FILE)

    with patch("homeassistant.components.filesize.config_flow.pathlib.Path",), patch(
        "homeassistant.components.filesize.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_FILE_PATH: TEST_FILE,
            },
        )

    assert result2["errors"] == {"base": "not_allowed"}

    hass.config.allowlist_external_dirs = {TEST_DIR}
    with patch("homeassistant.components.filesize.config_flow.pathlib.Path",), patch(
        "homeassistant.components.filesize.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_FILE_PATH: TEST_FILE,
            },
        )

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == TEST_FILE_NAME
    assert result2["data"] == {
        CONF_FILE_PATH: TEST_FILE,
    }
