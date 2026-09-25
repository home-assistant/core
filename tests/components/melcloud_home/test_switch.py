"""Tests for the MELCloud Home switch platform."""

from unittest.mock import AsyncMock, patch

from aiomelcloudhome.exceptions import (
    MelCloudHomeAuthenticationError,
    MelCloudHomeConnectionError,
    MelCloudHomeTimeoutError,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def enable_all_entities(entity_registry_enabled_by_default: None) -> None:
    """Make sure all entities are enabled."""


@pytest.mark.usefixtures("mock_melcloud_client")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all switch entities."""
    with patch(
        "homeassistant.components.melcloud_home.PLATFORMS",
        [Platform.SWITCH],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


@pytest.mark.parametrize(
    ("entity_id", "method", "base_kwargs"),
    [
        (
            "switch.living_room_ac_frost_protection",
            "set_frost_protection",
            {
                "min_temp": 10.0,
                "max_temp": 12.0,
                "ata_unit_ids": ["ata-unit-uuid-1"],
            },
        ),
        (
            "switch.living_room_ac_overheat_protection",
            "set_overheat_protection",
            {
                "min_temp": 35.0,
                "max_temp": 37.0,
                "ata_unit_ids": ["ata-unit-uuid-1"],
            },
        ),
        (
            "switch.heat_pump_frost_protection",
            "set_frost_protection",
            {
                "min_temp": 5.0,
                "max_temp": 8.0,
                "atw_unit_ids": ["atw-unit-uuid-1"],
            },
        ),
        (
            "switch.heat_pump_overheat_protection",
            "set_overheat_protection",
            {
                "min_temp": 40.0,
                "max_temp": 42.0,
                "atw_unit_ids": ["atw-unit-uuid-1"],
            },
        ),
    ],
)
@pytest.mark.parametrize("service_call", [SERVICE_TURN_ON, SERVICE_TURN_OFF])
async def test_turn_on_off(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    method: str,
    base_kwargs: dict,
    service_call: str,
) -> None:
    """Test switch turn on/off calls the correct API method."""
    await setup_integration(hass, mock_config_entry)

    method_mock = getattr(mock_melcloud_client, method)
    enabled = service_call == SERVICE_TURN_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service_call,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    method_mock.assert_called_once_with(enabled=enabled, **base_kwargs)


@pytest.mark.parametrize(
    ("entity_id", "method"),
    [
        ("switch.living_room_ac_frost_protection", "set_frost_protection"),
        ("switch.living_room_ac_overheat_protection", "set_overheat_protection"),
        ("switch.heat_pump_frost_protection", "set_frost_protection"),
        ("switch.heat_pump_overheat_protection", "set_overheat_protection"),
    ],
)
@pytest.mark.parametrize("service_call", [SERVICE_TURN_ON, SERVICE_TURN_OFF])
@pytest.mark.parametrize(
    ("raise_exception", "expected_exception"),
    [
        (MelCloudHomeAuthenticationError, HomeAssistantError),
        (MelCloudHomeConnectionError, HomeAssistantError),
        (MelCloudHomeTimeoutError, HomeAssistantError),
    ],
)
async def test_turn_on_off_exceptions(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    method: str,
    service_call: str,
    raise_exception: type[Exception],
    expected_exception: type[Exception],
) -> None:
    """Test switch actions raise HomeAssistantError on client errors."""
    await setup_integration(hass, mock_config_entry)

    method_mock = getattr(mock_melcloud_client, method)
    method_mock.side_effect = raise_exception

    with pytest.raises(expected_exception):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service_call,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
