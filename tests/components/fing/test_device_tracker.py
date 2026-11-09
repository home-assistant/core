"""Test Fing Agent device tracker entity."""

from datetime import timedelta

from fing_agent_api.models import DeviceResponse
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    AsyncMock,
    async_fire_time_changed,
    async_load_json_object_fixture,
    snapshot_platform,
)
from pytest_homeassistant.plugins import MockConfigEntry, SnapshotAssertion

from homeassistant.components.fing.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import init_integration


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mocked_fing_agent: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities created by Fing with snapshot."""
    entry = await init_integration(hass, mock_config_entry, mocked_fing_agent)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_new_device_found(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mocked_fing_agent: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test Fing device tracker setup."""

    delta_time = timedelta(seconds=35)  # 30 seconds + 5 delta seconds

    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")
    entry = await init_integration(hass, mock_config_entry, mocked_fing_agent)

    # First check -> there are 3 devices in total
    assert len(er.async_entries_for_config_entry(entity_registry, entry.entry_id)) == 3
    assert len(dr.async_entries_for_config_entry(device_registry, entry.entry_id)) == 3

    mocked_fing_agent.get_devices.return_value = DeviceResponse(
        await async_load_json_object_fixture(
            hass, "device_resp_device_added.json", DOMAIN
        )
    )

    freezer.tick(delta_time)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Second check -> added one device
    assert len(er.async_entries_for_config_entry(entity_registry, entry.entry_id)) == 4
    assert len(dr.async_entries_for_config_entry(device_registry, entry.entry_id)) == 4

    mocked_fing_agent.get_devices.return_value = DeviceResponse(
        await async_load_json_object_fixture(
            hass, "device_resp_device_deleted.json", DOMAIN
        )
    )

    freezer.tick(delta_time)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Third check -> removed two devices (old devices)
    assert len(er.async_entries_for_config_entry(entity_registry, entry.entry_id)) == 2
    assert len(dr.async_entries_for_config_entry(device_registry, entry.entry_id)) == 2


async def test_device_modified(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mocked_fing_agent: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test Fing device modified."""

    delta_time = timedelta(seconds=35)  # 30 seconds + 5 delta seconds

    # ----------------------------------------------------

    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")
    entry = await init_integration(hass, mock_config_entry, mocked_fing_agent)

    old_entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    device_entry = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, "00:00:00:00:00:03"), entry.entry_id
    )
    assert device_entry.name == "PC_HOME"

    # ----------------------------------------------------

    mocked_fing_agent.get_devices.return_value = DeviceResponse(
        await async_load_json_object_fixture(
            hass, "device_resp_device_modified.json", DOMAIN
        )
    )

    freezer.tick(delta_time)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    new_entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)

    # ----------------------------------------------------

    assert len(old_entries) == len(new_entries)

    old_entries_by_ids = {e.unique_id: e for e in old_entries}
    new_entries_by_ids = {e.unique_id: e for e in new_entries}

    unique_id = "0000000000XX-00:00:00:00:00:03"

    old_entry = old_entries_by_ids[unique_id]
    new_entry = new_entries_by_ids[unique_id]

    assert old_entry.original_icon != new_entry.original_icon
    assert old_entry.device_id == new_entry.device_id
    device_entry = device_registry.async_get(new_entry.device_id)
    assert device_entry.name == "NEW_PC_HOME"
    assert hass.states.get(new_entry.entity_id).name == "NEW_PC_HOME"


@pytest.mark.parametrize(
    ("name", "expected_name"),
    [
        pytest.param("PC_HOME", "PC_HOME", id="named"),
        pytest.param(None, "00:00:00:00:00:03", id="unnamed"),
    ],
)
async def test_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mocked_fing_agent: AsyncMock,
    device_registry: dr.DeviceRegistry,
    name: str | None,
    expected_name: str,
) -> None:
    """Test the tracked device is named by its Fing name, else by MAC address."""
    devices = await async_load_json_object_fixture(
        hass, "device_resp_new_API.json", DOMAIN
    )
    devices["devices"][2]["name"] = name
    mocked_fing_agent.get_devices.return_value = DeviceResponse(devices)
    entry = await init_integration(hass, mock_config_entry, mocked_fing_agent)

    device_entry = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, "00:00:00:00:00:03"), entry.entry_id
    )
    assert device_entry is not None
    assert device_entry.name == expected_name
