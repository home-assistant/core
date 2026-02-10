"""Define tests for the generic (IP camera) integration."""

import pytest

from homeassistant.components.generic.const import (
    CONF_CONTENT_TYPE,
    CONF_FRAMERATE,
    CONF_LIMIT_REFETCH_TO_URL_CHANGE,
    CONF_STILL_IMAGE_URL,
    CONF_STREAM_SOURCE,
    DOMAIN,
    SECTION_ADVANCED,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("fakeimg_png")
async def test_unload_entry(hass: HomeAssistant, setup_entry: MockConfigEntry) -> None:
    """Test unloading the generic IP Camera entry."""
    assert setup_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(setup_entry.entry_id)
    await hass.async_block_till_done()
    assert setup_entry.state is ConfigEntryState.NOT_LOADED


async def test_reload_on_title_change(
    hass: HomeAssistant, setup_entry: MockConfigEntry
) -> None:
    """Test the integration gets reloaded when the title is updated."""
    assert setup_entry.state is ConfigEntryState.LOADED
    assert (
        hass.states.get("camera.test_camera").attributes["friendly_name"]
        == "Test Camera"
    )

    hass.config_entries.async_update_entry(setup_entry, title="New Title")
    assert setup_entry.title == "New Title"
    await hass.async_block_till_done()

    assert (
        hass.states.get("camera.test_camera").attributes["friendly_name"] == "New Title"
    )


@pytest.mark.usefixtures("fakeimg_png")
async def test_migration_to_version_2(hass: HomeAssistant) -> None:
    """Test the File sensor with JSON entries."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Test Camera",
        unique_id="abc123",
        data={},
        options={
            CONF_STILL_IMAGE_URL: "http://joebloggs:letmein1@example.com/secret1/file.jpg?pw=qwerty",
            CONF_STREAM_SOURCE: "http://janebloggs:letmein2@example.com/stream",
            CONF_USERNAME: "johnbloggs",
            CONF_PASSWORD: "letmein123",
            CONF_LIMIT_REFETCH_TO_URL_CHANGE: False,
            CONF_AUTHENTICATION: HTTP_BASIC_AUTHENTICATION,
            CONF_FRAMERATE: 2.0,
            CONF_VERIFY_SSL: True,
            CONF_CONTENT_TYPE: "image/jpeg",
        },
        version=1,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 2
    assert entry.options == {
        CONF_STILL_IMAGE_URL: "http://joebloggs:letmein1@example.com/secret1/file.jpg?pw=qwerty",
        CONF_STREAM_SOURCE: "http://janebloggs:letmein2@example.com/stream",
        CONF_USERNAME: "johnbloggs",
        CONF_PASSWORD: "letmein123",
        CONF_CONTENT_TYPE: "image/jpeg",
        SECTION_ADVANCED: {
            CONF_FRAMERATE: 2.0,
            CONF_VERIFY_SSL: True,
            CONF_LIMIT_REFETCH_TO_URL_CHANGE: False,
            CONF_AUTHENTICATION: HTTP_BASIC_AUTHENTICATION,
        },
    }
