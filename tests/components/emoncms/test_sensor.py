"""Test emoncms sensor."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.emoncms.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration
from .conftest import EMONCMS_FAILURE, UNIQUE_ID, get_feed


async def test_no_feed_selected(
    hass: HomeAssistant,
    config_no_feed: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    emoncms_client: AsyncMock,
) -> None:
    """Test with no feed selected."""
    await setup_integration(hass, config_no_feed)

    assert config_no_feed.state is ConfigEntryState.LOADED
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_no_feed.entry_id
    )
    assert entity_entries == []


async def test_no_feed_broadcast(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    emoncms_client: AsyncMock,
) -> None:
    """Test with no feed broadcasted."""
    emoncms_client.async_request.return_value = {"success": True, "message": []}
    await setup_integration(hass, config_entry)

    assert config_entry.state is ConfigEntryState.LOADED
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    assert entity_entries == []


async def test_coordinator_update(
    hass: HomeAssistant,
    config_single_feed: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    emoncms_client: AsyncMock,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator update."""
    emoncms_client.async_request.return_value = {
        "success": True,
        "message": [get_feed(1, unit="°C")],
    }
    await setup_integration(hass, config_single_feed)

    await snapshot_platform(
        hass, entity_registry, snapshot, config_single_feed.entry_id
    )

    async def skip_time() -> None:
        freezer.tick(60)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    emoncms_client.async_request.return_value = {
        "success": True,
        "message": [get_feed(1, unit="°C", value=24.04, timestamp=1665509670)],
    }

    await skip_time()

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_single_feed.entry_id
    )

    for entity_entry in entity_entries:
        state = hass.states.get(entity_entry.entity_id)
        assert state.attributes["LastUpdated"] == 1665509670
        assert state.state == "24.04"

    emoncms_client.async_request.return_value = EMONCMS_FAILURE

    await skip_time()

    assert f"Error fetching {DOMAIN}_coordinator data" in caplog.text


async def test_feeds_grouped_by_tag(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    emoncms_client: AsyncMock,
) -> None:
    """Test each feed tag becomes a device holding its feeds."""
    garage = [{**get_feed(i, unit="°C"), "tag": "garage"} for i in (1, 2)]
    emoncms_client.async_request.return_value = {
        "success": True,
        "message": [*garage, get_feed(3, unit="xyz")],
    }
    await setup_integration(hass, config_entry)

    devices = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    assert sorted(device.name for device in devices) == ["garage", "tag"]
    garage_device = next(device for device in devices if device.name == "garage")
    assert len(er.async_entries_for_device(entity_registry, garage_device.id)) == 2
    assert hass.states.get("sensor.tag_parameter_3").name == "tag parameter 3"


async def test_upgrade_prefixes_custom_name_with_tag(
    hass: HomeAssistant,
    config_entry_unique_id: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    emoncms_client: AsyncMock,
) -> None:
    """Test a renamed entity from before tag devices keeps its id and gains the tag."""
    config_entry_unique_id.add_to_hass(hass)
    entity = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{UNIQUE_ID}-1",
        config_entry=config_entry_unique_id,
        suggested_object_id="kitchen_power",
    )
    entity_registry.async_update_entity(entity.entity_id, name="Kitchen power")
    assert entity.device_id is None

    await setup_integration(hass, config_entry_unique_id)

    assert entity_registry.async_get(entity.entity_id).device_id is not None
    assert hass.states.get(entity.entity_id).name == "tag Kitchen power"


async def test_untagged_device_survives_url_change(
    hass: HomeAssistant,
    config_entry_unique_id: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    emoncms_client: AsyncMock,
) -> None:
    """Test the untagged feeds device is kept when the server address changes."""
    emoncms_client.async_request.return_value = {
        "success": True,
        "message": [{**get_feed(1), "tag": ""}],
    }
    await setup_integration(hass, config_entry_unique_id)
    (device,) = dr.async_entries_for_config_entry(
        device_registry, config_entry_unique_id.entry_id
    )

    hass.config_entries.async_update_entry(
        config_entry_unique_id,
        data={**config_entry_unique_id.data, CONF_URL: "http://1.1.1.3"},
    )
    await hass.config_entries.async_reload(config_entry_unique_id.entry_id)
    await hass.async_block_till_done()

    (reloaded,) = dr.async_entries_for_config_entry(
        device_registry, config_entry_unique_id.entry_id
    )
    assert reloaded.id == device.id
    assert reloaded.name == "emoncms@1.1.1.3"
