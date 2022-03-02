"""Test the DlnaDmsData domain data storage class.

Some of the functionality it provides would normally be done by the entity
platform, but DmsDeviceSource is not an entity and DlnaDmsData is not a
platform, so things are done manually.
"""
from typing import Final

import pytest

from homeassistant.components.dlna_dms.const import DOMAIN
from homeassistant.components.dlna_dms.dms import DmsDeviceSource, get_domain_data
from homeassistant.const import CONF_DEVICE_ID, CONF_URL
from homeassistant.core import HomeAssistant

from .conftest import MOCK_DEVICE_NAME, MOCK_DEVICE_TYPE, MOCK_SOURCE_ID

from tests.common import MockConfigEntry

# Auto-use a few fixtures from conftest
pytestmark = [
    # Block network access
    pytest.mark.usefixtures("aiohttp_session_requester_mock"),
    pytest.mark.usefixtures("dms_device_mock"),
    # Setup the media_source platform
    pytest.mark.usefixtures("setup_media_source"),
]


async def test_generate_source_id(hass: HomeAssistant) -> None:
    """Test source IDs are generated without collision."""
    domain_data = get_domain_data(hass)
    assert domain_data.sources == {}

    # Add multiple sources with the same name to generate collisions
    for i in range(3):
        config_entry = MockConfigEntry(
            unique_id=f"udn-{i}::{MOCK_DEVICE_TYPE}",
            domain=DOMAIN,
            data={
                CONF_URL: "http://192.88.99.22/dms_description.xml",
                CONF_DEVICE_ID: f"different-udn::{MOCK_DEVICE_TYPE}",
            },
            title="Mock title",
        )
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.async_block_till_done()

    # Check the source IDs have not collided
    assert domain_data.sources.keys() == {"mock_title", "mock_title_1", "mock_title_2"}
    for source_id in domain_data.sources:
        assert domain_data.sources[source_id].source_id == source_id


async def test_update_source_id(
    hass: HomeAssistant,
    config_entry_mock: MockConfigEntry,
    device_source_mock: DmsDeviceSource,
) -> None:
    """Test the config listener updates the source_id and source list upon title change."""
    domain_data = get_domain_data(hass)
    assert domain_data.sources.keys() == {MOCK_SOURCE_ID}

    new_title: Final = "New Name"
    new_source_id: Final = "new_name"
    hass.config_entries.async_update_entry(config_entry_mock, title=new_title)
    await hass.async_block_till_done()

    assert device_source_mock.source_id == new_source_id
    assert domain_data.sources.keys() == {new_source_id}


async def test_update_existing_source_id(
    hass: HomeAssistant,
    config_entry_mock: MockConfigEntry,
    device_source_mock: DmsDeviceSource,
) -> None:
    """Test the config listener gracefully handles colliding source_id."""
    domain_data = get_domain_data(hass)
    new_title: Final = "New Name"
    new_source_id: Final = "new_name"
    new_source_id_2: Final = "new_name_1"
    # Set up another config entry to collide with the new source_id
    colliding_entry = MockConfigEntry(
        unique_id=f"different-udn::{MOCK_DEVICE_TYPE}",
        domain=DOMAIN,
        data={
            CONF_URL: "http://192.88.99.22/dms_description.xml",
            CONF_DEVICE_ID: f"different-udn::{MOCK_DEVICE_TYPE}",
        },
        title=new_title,
    )
    colliding_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(colliding_entry.entry_id)
    await hass.async_block_till_done()

    assert device_source_mock.source_id == MOCK_SOURCE_ID
    assert domain_data.sources.keys() == {MOCK_SOURCE_ID, new_source_id}
    assert domain_data.sources[MOCK_SOURCE_ID] is device_source_mock

    # Update the existing entry to match the other entry's name
    hass.config_entries.async_update_entry(config_entry_mock, title=new_title)
    await hass.async_block_till_done()

    # The existing device's source ID should be a newly generated slug
    assert device_source_mock.source_id == new_source_id_2
    assert domain_data.sources.keys() == {new_source_id, new_source_id_2}
    assert domain_data.sources[new_source_id_2] is device_source_mock

    # Changing back to the old name should not cause issues
    hass.config_entries.async_update_entry(config_entry_mock, title=MOCK_DEVICE_NAME)
    await hass.async_block_till_done()

    assert device_source_mock.source_id == MOCK_SOURCE_ID
    assert domain_data.sources.keys() == {MOCK_SOURCE_ID, new_source_id}
    assert domain_data.sources[MOCK_SOURCE_ID] is device_source_mock

    # Remove the collision and try again
    await hass.config_entries.async_remove(colliding_entry.entry_id)
    assert domain_data.sources.keys() == {MOCK_SOURCE_ID}

    hass.config_entries.async_update_entry(config_entry_mock, title=new_title)
    await hass.async_block_till_done()

    assert device_source_mock.source_id == new_source_id
    assert domain_data.sources.keys() == {new_source_id}
