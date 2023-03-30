"""Tests for the switch module."""
import pytest
import requests_mock
from syrupy import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.vesync import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .common import ALL_DEVICE_NAMES, mock_devices_response

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.mark.parametrize("device_name", ALL_DEVICE_NAMES)
async def test_switch_state(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    requests_mock: requests_mock.Mocker,
    device_name: str,
) -> None:
    """Test the resulting setup state is as expected for the platform."""
    requests_mock.post(
        "https://smartapi.vesync.com/cloud/v1/user/login",
        json=load_json_object_fixture("vesync/vesync_api_call__login.json"),
    )
    mock_devices_response(requests_mock, device_name)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert (
        dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
        == snapshot
    )

    entities = [
        entity
        for entity in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entity.domain == SWITCH_DOMAIN
    ]
    assert entities == snapshot

    for entity in entities:
        assert hass.states.get(entity.entity_id) == snapshot(name=entity.entity_id)
