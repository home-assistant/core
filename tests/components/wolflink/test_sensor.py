"""Test the Wolf SmartSet Service Sensor platform."""

from collections.abc import Generator
from unittest.mock import MagicMock

import pytest
from syrupy import SnapshotAssertion
from wolf_comm import (
    EnergyParameter,
    HoursParameter,
    ListItemParameter,
    PercentageParameter,
    PowerParameter,
    Pressure,
    SimpleParameter,
    Temperature,
)

from homeassistant.components.wolflink.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, patch, snapshot_platform


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Wolf SmartSet",
        domain=DOMAIN,
        data={
            "device_id": 1234,
            "device_name": "test-device",
            "device_gateway": 5678,
            "username": "test-username",
            "password": "test-password",
        },
        unique_id="1234",
        version=1,
        minor_version=2,
    )


@pytest.fixture
def mock_wolflink() -> Generator[MagicMock]:
    """Return a mocked wolflink client."""
    with (
        patch(
            "homeassistant.components.wolflink.WolfClient", autospec=True
        ) as wolflink_mock,
        patch(
            "homeassistant.components.wolflink.config_flow.WolfClient",
            new=wolflink_mock,
        ),
    ):
        wolflink = wolflink_mock.return_value

        wolflink.Parameters = [
            EnergyParameter(6002800000, "Energy Parameter", "Heating", 6005200000),
            ListItemParameter(
                8002800000,
                "List Item Parameter",
                "Heating",
                (["Pump", 0], ["Heating", 1]),
                8005200000,
            ),
            PowerParameter(5002800000, "Power Parameter", "Heating", 5005200000),
            Pressure(4002800000, "Pressure Parameter", "Heating", 4005200000),
            Temperature(3002800000, "Temperature Parameter", "Solar", 3005200000),
            PercentageParameter(
                2002800000, "Percentage Parameter", "Solar", 2005200000
            ),
            HoursParameter(7002800000, "Hours Parameter", "Heating", 7005200000),
            SimpleParameter(1002800000, "Simple Parameter", "DHW", 1005200000),
        ]

        yield wolflink


async def test_device_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    mock_wolflink: MagicMock,
) -> None:
    """Test device entry creation."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device({(mock_config_entry.domain, "1234")})
    assert device == snapshot


async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_wolflink: MagicMock,
) -> None:
    """Test wolflink sensors."""

    with patch("homeassistant.components.wolflink.PLATFORMS", [Platform.SENSOR]):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Ensure the entity registry is populated with mock_wolflink entities
    for parameter in mock_wolflink.Parameters:
        entity_id = entity_registry.async_get_or_create(
            domain=Platform.SENSOR,
            platform=DOMAIN,
            unique_id=f"{'1234'}-{parameter.parameter_id}",
            config_entry=mock_config_entry,
            suggested_object_id=parameter.name,
        ).entity_id

        hass.states.async_set(
            entity_id,
            "10",
        )

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
