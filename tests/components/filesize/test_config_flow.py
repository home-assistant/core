"""Tests for the Filesize config flow."""

from pathlib import Path
from unittest.mock import patch

import pytest

from homeassistant.components.filesize.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_FILE_PATH
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import TEST_FILE_NAME, async_create_file

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_full_user_flow(hass: HomeAssistant, tmp_path: Path) -> None:
    """Test the full user configuration flow."""
    test_file = str(tmp_path.joinpath(TEST_FILE_NAME))
    await async_create_file(hass, test_file)
    hass.config.allowlist_external_dirs = {tmp_path}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_FILE_PATH: test_file},
    )

    assert result2.get("type") is FlowResultType.CREATE_ENTRY
    assert result2.get("title") == TEST_FILE_NAME
    assert result2.get("data") == {CONF_FILE_PATH: test_file}


async def test_unique_path(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, tmp_path: Path
) -> None:
    """Test we abort if already setup."""
    test_file = str(tmp_path.joinpath(TEST_FILE_NAME))
    await async_create_file(hass, test_file)
    hass.config.allowlist_external_dirs = {tmp_path}
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={CONF_FILE_PATH: test_file}
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_flow_fails_on_validation(hass: HomeAssistant, tmp_path: Path) -> None:
    """Test config flow errors."""
    test_file = str(tmp_path.joinpath(TEST_FILE_NAME))
    hass.config.allowlist_external_dirs = {}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_FILE_PATH: test_file,
        },
    )

    assert result2["errors"] == {"base": "not_valid"}

    await async_create_file(hass, test_file)

    with patch(
        "homeassistant.components.filesize.config_flow.pathlib.Path",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_FILE_PATH: test_file,
            },
        )

    assert result2["errors"] == {"base": "not_allowed"}

    hass.config.allowlist_external_dirs = {tmp_path}
    with patch(
        "homeassistant.components.filesize.config_flow.pathlib.Path",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_FILE_PATH: test_file,
            },
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == TEST_FILE_NAME
    assert result2["data"] == {
        CONF_FILE_PATH: test_file,
    }
