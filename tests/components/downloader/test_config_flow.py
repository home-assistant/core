"""Test the Downloader config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.downloader.config_flow import CannotConnect
from homeassistant.components.downloader.const import CONF_DOWNLOAD_DIR, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

CONFIG = {CONF_DOWNLOAD_DIR: "download_dir"}


async def test_user_form(hass: HomeAssistant) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.downloader.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG,
        )
        assert result["type"] == FlowResultType.FORM

        with patch(
            "homeassistant.components.downloader.config_flow.DownloaderConfigFlow._validate_input",
            side_effect=CannotConnect,
        ):
            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "user"
            assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.downloader.async_setup_entry", return_value=True
    ), patch(
        "homeassistant.components.downloader.config_flow.DownloaderConfigFlow._validate_input",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONFIG,
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Downloader"
        assert result["data"] == {"download_dir": "download_dir"}


@pytest.mark.parametrize("source", [SOURCE_USER, SOURCE_IMPORT])
async def test_single_instance_allowed(
    hass: HomeAssistant,
    source: str,
) -> None:
    """Test we abort if already setup."""
    mock_config_entry = MockConfigEntry(domain=DOMAIN)

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": source}
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_import_flow_success(hass: HomeAssistant) -> None:
    """Test import flow."""
    with patch(
        "homeassistant.components.downloader.async_setup_entry", return_value=True
    ), patch(
        "homeassistant.components.downloader.config_flow.DownloaderConfigFlow._validate_input",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={},
        )
        await hass.async_block_till_done()

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Downloader"
        assert result["data"] == {}
        assert result["options"] == {}
