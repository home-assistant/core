"""Test the Folder Watcher config flow."""

from pathlib import Path
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.folder_watcher.const import (
    CONF_FOLDER,
    CONF_PATTERNS,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_form(hass: HomeAssistant, tmp_path: Path) -> None:
    """Test we get the form."""
    path = tmp_path.as_posix()
    hass.config.allowlist_external_dirs = {path}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_FOLDER: path},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Folder Watcher {path}"
    assert result["options"] == {CONF_FOLDER: path, CONF_PATTERNS: ["*"]}


async def test_form_not_allowed_path(hass: HomeAssistant, tmp_path: Path) -> None:
    """Test we handle not allowed path."""
    path = tmp_path.as_posix()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_FOLDER: path},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "not_allowed_dir"}

    hass.config.allowlist_external_dirs = {tmp_path}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_FOLDER: path},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Folder Watcher {path}"
    assert result["options"] == {CONF_FOLDER: path, CONF_PATTERNS: ["*"]}


async def test_form_not_directory(hass: HomeAssistant, tmp_path: Path) -> None:
    """Test we handle not a directory."""
    path = tmp_path.as_posix()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_FOLDER: "not_a_directory"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "not_dir"}

    hass.config.allowlist_external_dirs = {path}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_FOLDER: path},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Folder Watcher {path}"
    assert result["options"] == {CONF_FOLDER: path, CONF_PATTERNS: ["*"]}


async def test_form_not_readable_dir(hass: HomeAssistant, tmp_path: Path) -> None:
    """Test we handle not able to read directory."""
    path = tmp_path.as_posix()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("os.access", return_value=False):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_FOLDER: path},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "not_readable_dir"}

    hass.config.allowlist_external_dirs = {path}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_FOLDER: path},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Folder Watcher {path}"
    assert result["options"] == {CONF_FOLDER: path, CONF_PATTERNS: ["*"]}


async def test_form_already_configured(hass: HomeAssistant, tmp_path: Path) -> None:
    """Test we abort when entry is already configured."""
    path = tmp_path.as_posix()
    hass.config.allowlist_external_dirs = {path}

    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Folder Watcher {path}",
        data={CONF_FOLDER: path},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_FOLDER: path},
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import(hass: HomeAssistant, tmp_path: Path) -> None:
    """Test import flow."""
    path = tmp_path.as_posix()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={CONF_FOLDER: path, CONF_PATTERNS: ["*"]},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Folder Watcher {path}"
    assert result["options"] == {CONF_FOLDER: path, CONF_PATTERNS: ["*"]}


async def test_import_already_configured(hass: HomeAssistant, tmp_path: Path) -> None:
    """Test we abort import when entry is already configured."""
    path = tmp_path.as_posix()

    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Folder Watcher {path}",
        data={CONF_FOLDER: path},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={CONF_FOLDER: path},
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
