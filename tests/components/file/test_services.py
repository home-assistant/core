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
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
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


async def test_read_file_disallowed_path(
    hass: HomeAssistant,
) -> None:
    """Test the notify file output."""
    await _setup_hass(hass)

    file_name = "tests/components/file/fixtures/file_read.json"

    with pytest.raises(HomeAssistantError) as hae:
        _ = await hass.services.async_call(
            FILE_DOMAIN,
            SERVICE_READ_FILE,
            {
                ATTR_FILE_NAME: file_name,
                ATTR_FILE_ENCODING: "json",
            },
            blocking=True,
            return_response=True,
        )
    assert file_name in str(hae.value)


async def test_read_file_bad_encoding(
    hass: HomeAssistant,
    mock_is_allowed_path: MagicMock,
) -> None:
    """Test the notify file output."""
    await _setup_hass(hass)

    file_name = "tests/components/file/fixtures/file_read.json"

    with pytest.raises(ServiceValidationError) as sve:
        _ = await hass.services.async_call(
            FILE_DOMAIN,
            SERVICE_READ_FILE,
            {
                ATTR_FILE_NAME: file_name,
                ATTR_FILE_ENCODING: "invalid",
            },
            blocking=True,
            return_response=True,
        )
    assert file_name in str(sve.value)
    assert "invalid" in str(sve.value)


@pytest.mark.parametrize(
    ("file_name", "file_encoding"),
    [
        ("tests/components/file/fixtures/file_read.yaml", "json"),
        ("tests/components/file/fixtures/file_read.not_yaml", "yaml"),
    ],
)
async def test_read_file_decoding_error(
    hass: HomeAssistant,
    mock_is_allowed_path: MagicMock,
    file_name: str,
    file_encoding: str,
) -> None:
    """Test the notify file output."""
    await _setup_hass(hass)

    with pytest.raises(HomeAssistantError) as hae:
        _ = await hass.services.async_call(
            FILE_DOMAIN,
            SERVICE_READ_FILE,
            {
                ATTR_FILE_NAME: file_name,
                ATTR_FILE_ENCODING: file_encoding,
            },
            blocking=True,
            return_response=True,
        )
    assert file_name in str(hae.value)
    assert file_encoding in str(hae.value)
