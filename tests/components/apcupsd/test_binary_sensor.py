"""Test binary sensors of APCUPSd integration."""

from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.apcupsd.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import slugify

from . import MOCK_STATUS

from tests.common import MockConfigEntry, snapshot_platform

pytestmark = pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "init_integration"
)


@pytest.fixture
def platforms() -> list[Platform]:
    """Overridden fixture to specify platforms to test."""
    return [Platform.BINARY_SENSOR]


async def test_binary_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_request_status: AsyncMock,
) -> None:
    """Test states of binary sensor entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    # Ensure entities are correctly assigned to device
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_request_status.return_value["SERIALNO"])}
    )
    assert device_entry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_entry.device_id == device_entry.id


@pytest.mark.parametrize(
    "mock_request_status",
    [{k: v for k, v in MOCK_STATUS.items() if k != "STATFLAG"}],
    indirect=True,
)
async def test_no_binary_sensor(
    hass: HomeAssistant,
    mock_request_status: AsyncMock,
) -> None:
    """Test binary sensor when STATFLAG is not available."""
    device_slug = slugify(mock_request_status.return_value["UPSNAME"])
    state = hass.states.get(f"binary_sensor.{device_slug}_online_status")
    assert state is None


@pytest.mark.parametrize(
    ("mock_request_status", "expected"),
    [
        (MOCK_STATUS | {"STATFLAG": "0x008"}, "on"),
        (MOCK_STATUS | {"STATFLAG": "0x02040010 Status Flag"}, "off"),
    ],
    indirect=["mock_request_status"],
)
async def test_statflag(
    hass: HomeAssistant,
    mock_request_status: AsyncMock,
    expected: str,
) -> None:
    """Test binary sensor for different STATFLAG values."""
    device_slug = slugify(mock_request_status.return_value["UPSNAME"])
    state = hass.states.get(f"binary_sensor.{device_slug}_online_status")
    assert state.state == expected
