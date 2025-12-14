"""The tests for the notify file platform."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.file import DOMAIN
from homeassistant.components.file.services import (
    ATTR_FILE_ENCODING,
    ATTR_FILE_NAME,
    SERVICE_READ_FILE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError


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
    setup_ha_file_integration,
    file_name: str,
    file_encoding: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test reading files in supported formats."""
    result = await hass.services.async_call(
        DOMAIN,
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
    setup_ha_file_integration,
) -> None:
    """Test reading in a disallowed path generates error."""
    file_name = "tests/components/file/fixtures/file_read.json"

    with pytest.raises(ServiceValidationError) as sve:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_READ_FILE,
            {
                ATTR_FILE_NAME: file_name,
                ATTR_FILE_ENCODING: "json",
            },
            blocking=True,
            return_response=True,
        )
    assert file_name in str(sve.value)
    assert sve.value.translation_key == "no_access_to_path"
    assert sve.value.translation_domain == DOMAIN


async def test_read_file_bad_encoding_option(
    hass: HomeAssistant,
    mock_is_allowed_path: MagicMock,
    setup_ha_file_integration,
) -> None:
    """Test handling error if an invalid encoding is specified."""
    file_name = "tests/components/file/fixtures/file_read.json"

    with pytest.raises(ServiceValidationError) as sve:
        await hass.services.async_call(
            DOMAIN,
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
    assert sve.value.translation_key == "unsupported_file_encoding"
    assert sve.value.translation_domain == DOMAIN


@pytest.mark.parametrize(
    ("file_name", "file_encoding"),
    [
        ("tests/components/file/fixtures/file_read.not_json", "json"),
        ("tests/components/file/fixtures/file_read.not_yaml", "yaml"),
    ],
)
async def test_read_file_decoding_error(
    hass: HomeAssistant,
    mock_is_allowed_path: MagicMock,
    setup_ha_file_integration,
    file_name: str,
    file_encoding: str,
) -> None:
    """Test decoding errors are handled correctly."""
    with pytest.raises(HomeAssistantError) as hae:
        await hass.services.async_call(
            DOMAIN,
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
    assert hae.value.translation_key == "file_decoding"
    assert hae.value.translation_domain == DOMAIN


async def test_read_file_dne(
    hass: HomeAssistant,
    mock_is_allowed_path: MagicMock,
    setup_ha_file_integration,
) -> None:
    """Test handling error if file does not exist."""
    file_name = "tests/components/file/fixtures/file_dne.yaml"

    with pytest.raises(HomeAssistantError) as hae:
        _ = await hass.services.async_call(
            DOMAIN,
            SERVICE_READ_FILE,
            {
                ATTR_FILE_NAME: file_name,
                ATTR_FILE_ENCODING: "yaml",
            },
            blocking=True,
            return_response=True,
        )
    assert file_name in str(hae.value)
