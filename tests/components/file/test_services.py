"""The tests for the notify file platform."""

from unittest.mock import MagicMock

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.file import DOMAIN as FILE_DOMAIN
from homeassistant.components.file.services import (
    ATTR_FILE_ENCODING,
    ATTR_FILE_NAME,
    SERVICE_READ_FILE,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def _setup_hass(hass: HomeAssistant):
    await async_setup_component(
        hass,
        FILE_DOMAIN,
        {FILE_DOMAIN: {}},
    )
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("file_name", "file_encoding"),
    [
        ("tests/components/file/fixtures/file_read.json", "json"),
        ("tests/components/file/fixtures/file_read.yaml", "yaml"),
        ("tests/components/file/fixtures/file_read_list.yaml", "yaml"),
    ],
)
async def test_read_file(
    hass: HomeAssistant,
    mock_is_allowed_path: MagicMock,
    file_name: str,
    file_encoding: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the notify file output."""
    await _setup_hass(hass)

    result = await hass.services.async_call(
        FILE_DOMAIN,
        SERVICE_READ_FILE,
        {
            ATTR_FILE_NAME: file_name,
            ATTR_FILE_ENCODING: file_encoding,
        },
        blocking=True,
        return_response=True,
    )
    assert result == snapshot
