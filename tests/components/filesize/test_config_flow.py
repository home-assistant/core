"""Tests for the Filesize config flow."""

from pathlib import Path
from unittest.mock import patch

import pytest

from homeassistant.components.filesize.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_FILE_PATH
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import TEST_FILE_NAME, TEST_FILE_NAME2, async_create_file

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


async def test_reconfigure_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, tmp_path: Path
) -> None:
    """Test a reconfigure flow."""
    test_file = str(tmp_path.joinpath(TEST_FILE_NAME2))
    await async_create_file(hass, test_file)
    hass.config.allowlist_external_dirs = {tmp_path}
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_FILE_PATH: test_file},
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {CONF_FILE_PATH: str(test_file)}


async def test_unique_id_already_exist_in_reconfigure_flow(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """Test a reconfigure flow fails when unique id already exist."""
    test_file = str(tmp_path.joinpath(TEST_FILE_NAME))
    test_file2 = str(tmp_path.joinpath(TEST_FILE_NAME2))
    await async_create_file(hass, test_file)
    await async_create_file(hass, test_file2)
    hass.config.allowlist_external_dirs = {tmp_path}
    test_file = str(tmp_path.joinpath(TEST_FILE_NAME))
    mock_config_entry = MockConfigEntry(
        title=TEST_FILE_NAME,
        domain=DOMAIN,
        data={CONF_FILE_PATH: test_file},
        unique_id=test_file,
    )
    mock_config_entry2 = MockConfigEntry(
        title=TEST_FILE_NAME2,
        domain=DOMAIN,
        data={CONF_FILE_PATH: test_file2},
        unique_id=test_file2,
    )
    mock_config_entry.add_to_hass(hass)
    mock_config_entry2.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_FILE_PATH: test_file2},
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_reconfigure_flow_fails_on_validation(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, tmp_path: Path
) -> None:
    """Test config flow errors in reconfigure."""
    test_file2 = str(tmp_path.joinpath(TEST_FILE_NAME2))
    hass.config.allowlist_external_dirs = {}

    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_FILE_PATH: test_file2,
        },
    )

    assert result["errors"] == {"base": "not_valid"}

    await async_create_file(hass, test_file2)

    with patch(
        "homeassistant.components.filesize.config_flow.pathlib.Path",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_FILE_PATH: test_file2,
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
                CONF_FILE_PATH: test_file2,
            },
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"
