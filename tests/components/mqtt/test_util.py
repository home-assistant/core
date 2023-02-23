"""Test MQTT utils."""

from random import getrandbits
from unittest.mock import patch

import pytest

from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant


@pytest.fixture(autouse=True)
def mock_temp_dir():
    """Mock the certificate temp directory."""
    with patch(
        # Patch temp dir name to avoid tests fail running in parallel
        "homeassistant.components.mqtt.util.TEMP_DIR_NAME",
        "home-assistant-mqtt" + f"-{getrandbits(10):03x}",
    ) as mocked_temp_dir:
        yield mocked_temp_dir


@pytest.mark.parametrize(
    ("option", "content", "file_created"),
    [
        (mqtt.CONF_CERTIFICATE, "auto", False),
        (mqtt.CONF_CERTIFICATE, "### CA CERTIFICATE ###", True),
        (mqtt.CONF_CLIENT_CERT, "### CLIENT CERTIFICATE ###", True),
        (mqtt.CONF_CLIENT_KEY, "### PRIVATE KEY ###", True),
    ],
)
async def test_async_create_certificate_temp_files(
    hass: HomeAssistant, mock_temp_dir, option, content, file_created
) -> None:
    """Test creating and reading certificate files."""
    config = {option: content}
    await mqtt.util.async_create_certificate_temp_files(hass, config)

    file_path = mqtt.util.get_file_path(option)
    assert bool(file_path) is file_created
    assert (
        mqtt.util.migrate_certificate_file_to_content(file_path or content) == content
    )


async def test_reading_non_exitisting_certificate_file() -> None:
    """Test reading a non existing certificate file."""
    assert (
        mqtt.util.migrate_certificate_file_to_content("/home/file_not_exists") is None
    )
