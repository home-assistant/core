"""Tests for Roborock Q10 sensor platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from roborock import RoborockCategory
from roborock.data import HomeDataDevice, HomeDataProduct
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import FakeDevice, create_b01_q10_trait
from .mock_data import BASE_URL, Q10_HOME_DATA_DEVICE, ROBOROCK_RRUID, USER_DATA

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to set platforms used in the test."""
    return [Platform.SENSOR]


@pytest.fixture(name="q10_fake_device")
def q10_fake_device_fixture() -> FakeDevice:
    """Create a fake Q10 S5+ device for testing."""
    device_data = HomeDataDevice.from_dict(Q10_HOME_DATA_DEVICE)
    product_data = HomeDataProduct(
        id="q10_product_id",
        name="Roborock Q10 S5+",
        code="ss07",
        model="roborock.vacuum.ss07",
        category=RoborockCategory.VACUUM,
    )

    fake_device = FakeDevice(
        device_info=device_data,
        product=product_data,
    )
    fake_device.is_connected = True
    fake_device.is_local_connected = True
    fake_device.b01_q10_properties = create_b01_q10_trait()

    return fake_device


@pytest.fixture(name="q10_device_manager")
def q10_device_manager_fixture(q10_fake_device: FakeDevice) -> AsyncMock:
    """Fixture to create a fake device manager with Q10 device."""
    device_manager = AsyncMock()
    device_manager.get_devices = AsyncMock(return_value=[q10_fake_device])
    return device_manager


@pytest.fixture(name="q10_config_entry")
def q10_config_entry_fixture(hass: HomeAssistant) -> MockConfigEntry:
    """Create a Q10 config entry."""
    config_entry = MockConfigEntry(
        domain="roborock",
        title="user@domain.com",
        data={
            "username": "user@domain.com",
            "user_data": USER_DATA.as_dict(),
            "base_url": BASE_URL,
        },
        unique_id=ROBOROCK_RRUID,
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)
    return config_entry


async def test_q10_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    q10_config_entry: MockConfigEntry,
    q10_device_manager: AsyncMock,
    platforms: list[Platform],
    snapshot: SnapshotAssertion,
) -> None:
    """Test Q10 S5+ sensors and check values are correctly set."""
    with (
        patch("homeassistant.components.roborock.PLATFORMS", platforms),
        patch(
            "homeassistant.components.roborock.create_device_manager",
            return_value=q10_device_manager,
        ),
    ):
        await hass.config_entries.async_setup(q10_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, q10_config_entry.entry_id)
