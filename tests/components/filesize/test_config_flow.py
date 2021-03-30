"""Test the filesize config flow."""
import os
from unittest.mock import patch

import pytest

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.filesize.config_flow import NotAFile
from homeassistant.components.filesize.const import DOMAIN
from homeassistant.const import CONF_FILE_PATH, CONF_UNIT_OF_MEASUREMENT

from tests.common import MockConfigEntry

TEST_DIR = os.path.join(os.path.dirname(__file__))
TEST_FILE = os.path.join(TEST_DIR, "mock_file_test_filesize.txt")


TEST_DATA = {CONF_FILE_PATH: TEST_FILE, CONF_UNIT_OF_MEASUREMENT: "GB"}


def create_file(path):
    """Create a test file."""
    with open(path, "w") as test_file:
        test_file.write("test")


@pytest.fixture(autouse=True)
def remove_file():
    """Remove test file."""
    yield
    if os.path.isfile(TEST_FILE):
        os.remove(TEST_FILE)


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    hass.config.allowlist_external_dirs = TEST_DIR
    create_file(TEST_FILE)

    with patch(
        "homeassistant.components.filesize.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.filesize.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_FILE_PATH: TEST_FILE,
                CONF_UNIT_OF_MEASUREMENT: "GB",
            },
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == TEST_FILE + " (GB)"
    assert result2["data"] == {
        CONF_FILE_PATH: TEST_FILE,
        CONF_UNIT_OF_MEASUREMENT: "GB",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_path(hass):
    """Test we handle invalid path."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_FILE_PATH: "/dummy/invalid_test_path"},
    )

    assert result["type"] == "form"
    assert result["errors"] == {CONF_FILE_PATH: "invalid_path"}


async def test_form_not_a_file(hass):
    """Test we handle path that is not pointing to a file."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.filesize.config_flow.validate_input",
        side_effect=NotAFile,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_FILE_PATH: "./not_a_file"},
        )

    assert result["type"] == "form"
    assert result["errors"] == {CONF_FILE_PATH: "not_a_file"}


async def test_unload(hass):
    """Test being able to unload an entry."""
    create_file(TEST_FILE)
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_DATA,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
