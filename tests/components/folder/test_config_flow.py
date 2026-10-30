"""Test the Folder config flow."""

from pathlib import Path
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.folder.const import CONF_FILTER, CONF_FOLDER_PATHS, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form(hass: HomeAssistant, folder_path: str) -> None:
    """Test the user flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_FOLDER_PATHS: folder_path, CONF_FILTER: "*.txt"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == folder_path
    assert result["data"] == {}
    assert result["options"] == {CONF_FOLDER_PATHS: folder_path, CONF_FILTER: "*.txt"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_default_filter(hass: HomeAssistant, folder_path: str) -> None:
    """Test the filter defaults to matching all files."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_FOLDER_PATHS: folder_path}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {CONF_FOLDER_PATHS: folder_path, CONF_FILTER: "*"}


@pytest.mark.parametrize(
    ("path_name", "readable", "allowed_name", "error"),
    [
        pytest.param("missing", True, "test_folder", "not_dir", id="not_dir"),
        pytest.param(
            "test_folder", False, "test_folder", "not_readable_dir", id="unreadable"
        ),
        pytest.param(
            "test_folder", True, "other_folder", "not_allowed_dir", id="not_allowed"
        ),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_errors(
    hass: HomeAssistant,
    folder_path: str,
    tmp_path: Path,
    path_name: str,
    readable: bool,
    allowed_name: str,
    error: str,
) -> None:
    """Test errors are shown and the flow can recover."""
    hass.config.allowlist_external_dirs = {str(tmp_path / allowed_name)}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.folder.config_flow.os.access", return_value=readable
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_FOLDER_PATHS: str(tmp_path / path_name)}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    hass.config.allowlist_external_dirs = {folder_path}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_FOLDER_PATHS: folder_path}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, folder_path: str
) -> None:
    """Test the same folder and filter can't be added twice."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_FOLDER_PATHS: folder_path, CONF_FILTER: "*"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_same_folder_other_filter(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, folder_path: str
) -> None:
    """Test the same folder can be added again with another filter."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_FOLDER_PATHS: folder_path, CONF_FILTER: "*.txt"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, folder_path: str
) -> None:
    """Test the filter can't be changed to one another entry uses for the folder."""
    mock_config_entry.add_to_hass(hass)
    MockConfigEntry(
        domain=DOMAIN,
        title=folder_path,
        options={CONF_FOLDER_PATHS: folder_path, CONF_FILTER: "*.txt"},
    ).add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_FILTER: "*.txt"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.options[CONF_FILTER] == "*"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_options_flow_keep_filter(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test saving the entry's own filter again is not a duplicate."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_FILTER: "*"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_options_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, folder_path: str
) -> None:
    """Test the filter can be changed in the options flow."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_FILTER: "*.txt"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == {
        CONF_FOLDER_PATHS: folder_path,
        CONF_FILTER: "*.txt",
    }
    state = hass.states.get("sensor.test_folder")
    assert state
    assert state.attributes["filter"] == "*.txt"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import(hass: HomeAssistant, folder_path: str) -> None:
    """Test a YAML configuration is imported."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_FOLDER_PATHS: folder_path, CONF_FILTER: "*.txt"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == folder_path
    assert result["options"] == {CONF_FOLDER_PATHS: folder_path, CONF_FILTER: "*.txt"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_not_allowed(hass: HomeAssistant, folder_path: str) -> None:
    """Test a YAML configuration with a folder outside the allowlist is aborted."""
    hass.config.allowlist_external_dirs = set()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_FOLDER_PATHS: folder_path, CONF_FILTER: "*"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_allowed_dir"
