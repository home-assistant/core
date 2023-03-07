"""Test the Matter helpers."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from homeassistant.components.matter.const import DOMAIN
from homeassistant.components.matter.helpers import (
    get_device_id,
    get_node_from_device_entry,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .common import setup_integration_with_node_fixture

from tests.common import MockConfigEntry


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_get_device_id(
    hass: HomeAssistant,
    matter_client: MagicMock,
) -> None:
    """Test get_device_id."""
    node = await setup_integration_with_node_fixture(
        hass, "device_diagnostics", matter_client
    )
    device_id = get_device_id(matter_client.server_info, node.endpoints[0])

    assert device_id == "00000000000004D2-0000000000000005-MatterNodeDevice"


# This tests needs to be adjusted to remove lingering tasks
@pytest.mark.parametrize("expected_lingering_tasks", [True])
async def test_get_node_from_device_entry(
    hass: HomeAssistant,
    matter_client: MagicMock,
) -> None:
    """Test get_node_from_device_entry."""
    device_registry = dr.async_get(hass)
    other_domain = "other_domain"
    other_config_entry = MockConfigEntry(domain=other_domain)
    other_device_entry = device_registry.async_get_or_create(
        config_entry_id=other_config_entry.entry_id,
        identifiers={(other_domain, "1234")},
    )
    node = await setup_integration_with_node_fixture(
        hass, "device_diagnostics", matter_client
    )
    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    device_entry = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )[0]
    assert device_entry
    node_from_device_entry = await get_node_from_device_entry(hass, device_entry)

    assert node_from_device_entry is node

    with pytest.raises(ValueError) as value_error:
        await get_node_from_device_entry(hass, other_device_entry)

    assert f"Device {other_device_entry.id} is not a Matter device" in str(
        value_error.value
    )

    matter_client.server_info = None

    with pytest.raises(RuntimeError) as runtime_error:
        node_from_device_entry = await get_node_from_device_entry(hass, device_entry)

    assert "Matter server information is not available" in str(runtime_error.value)
