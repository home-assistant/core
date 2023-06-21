"""Tests for the filesize component."""

from homeassistant.core import HomeAssistant

TEST_FILE_NAME = "mock_file_test_filesize.txt"
TEST_FILE_NAME2 = "mock_file_test_filesize2.txt"


async def async_create_file(hass: HomeAssistant, path: str) -> None:
    """Create a test file."""
    await hass.async_add_executor_job(create_file, path)


def create_file(path: str) -> None:
    """Create the test file."""
    with open(path, "w", encoding="utf-8") as test_file:
        test_file.write("test")
