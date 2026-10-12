"""Tests for the MELCloud Home number platform."""

from unittest.mock import AsyncMock, patch

from aiomelcloudhome.exceptions import (
    MelCloudHomeAuthenticationError,
    MelCloudHomeConnectionError,
    MelCloudHomeTimeoutError,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
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
    """Test all number entities."""
    with patch(
        "homeassistant.components.melcloud_home.PLATFORMS",
        [Platform.NUMBER],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


@pytest.mark.parametrize(
    ("entity_id", "method", "expected_kwargs", "value"),
    [
        (
            "number.living_room_ac_frost_protection_minimum_temperature",
            "set_frost_protection",
            {
                "enabled": True,
                "min_temp": 11.0,
                "max_temp": 12.0,
                "ata_unit_ids": ["ata-unit-uuid-1"],
            },
            11.0,
        ),
        (
            "number.living_room_ac_frost_protection_maximum_temperature",
            "set_frost_protection",
            {
                "enabled": True,
                "min_temp": 10.0,
                "max_temp": 13.0,
                "ata_unit_ids": ["ata-unit-uuid-1"],
            },
            13.0,
        ),
        (
            "number.living_room_ac_overheat_protection_minimum_temperature",
            "set_overheat_protection",
            {
                "enabled": True,
                "min_temp": 36.0,
                "max_temp": 37.0,
                "ata_unit_ids": ["ata-unit-uuid-1"],
            },
            36.0,
        ),
        (
            "number.living_room_ac_overheat_protection_maximum_temperature",
            "set_overheat_protection",
            {
                "enabled": True,
                "min_temp": 35.0,
                "max_temp": 38.0,
                "ata_unit_ids": ["ata-unit-uuid-1"],
            },
            38.0,
        ),
        (
            "number.heat_pump_frost_protection_minimum_temperature",
            "set_frost_protection",
            {
                "enabled": True,
                "min_temp": 6.0,
                "max_temp": 8.0,
                "atw_unit_ids": ["atw-unit-uuid-1"],
            },
            6.0,
        ),
        (
            "number.heat_pump_frost_protection_maximum_temperature",
            "set_frost_protection",
            {
                "enabled": True,
                "min_temp": 5.0,
                "max_temp": 9.0,
                "atw_unit_ids": ["atw-unit-uuid-1"],
            },
            9.0,
        ),
        (
            "number.heat_pump_overheat_protection_minimum_temperature",
            "set_overheat_protection",
            {
                "enabled": True,
                "min_temp": 41.0,
                "max_temp": 42.0,
                "atw_unit_ids": ["atw-unit-uuid-1"],
            },
            41.0,
        ),
        (
            "number.heat_pump_overheat_protection_maximum_temperature",
            "set_overheat_protection",
            {
                "enabled": True,
                "min_temp": 40.0,
                "max_temp": 43.0,
                "atw_unit_ids": ["atw-unit-uuid-1"],
            },
            43.0,
        ),
    ],
)
async def test_set_value(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    method: str,
    expected_kwargs: dict,
    value: float,
) -> None:
    """Test number set_value calls the correct API method."""
    await setup_integration(hass, mock_config_entry)

    method_mock = getattr(mock_melcloud_client, method)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
        blocking=True,
    )

    method_mock.assert_called_once_with(**expected_kwargs)


@pytest.mark.parametrize(
    ("entity_id", "value"),
    [
        (
            "number.living_room_ac_frost_protection_minimum_temperature",
            12.0,
        ),
        (
            "number.living_room_ac_frost_protection_minimum_temperature",
            13.0,
        ),
        (
            "number.living_room_ac_frost_protection_maximum_temperature",
            10.0,
        ),
        (
            "number.living_room_ac_frost_protection_maximum_temperature",
            9.0,
        ),
        (
            "number.living_room_ac_overheat_protection_minimum_temperature",
            37.0,
        ),
        (
            "number.living_room_ac_overheat_protection_maximum_temperature",
            35.0,
        ),
        (
            "number.heat_pump_frost_protection_minimum_temperature",
            8.0,
        ),
        (
            "number.heat_pump_frost_protection_maximum_temperature",
            5.0,
        ),
        (
            "number.heat_pump_overheat_protection_minimum_temperature",
            42.0,
        ),
        (
            "number.heat_pump_overheat_protection_maximum_temperature",
            40.0,
        ),
    ],
)
async def test_set_value_validation_error(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    value: float,
) -> None:
    """Test that setting min >= max or max <= min raises HomeAssistantError."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
            blocking=True,
        )

    mock_melcloud_client.set_frost_protection.assert_not_called()
    mock_melcloud_client.set_overheat_protection.assert_not_called()


@pytest.mark.parametrize(
    ("entity_id", "method", "value"),
    [
        (
            "number.living_room_ac_frost_protection_minimum_temperature",
            "set_frost_protection",
            10.0,
        ),
        (
            "number.living_room_ac_frost_protection_maximum_temperature",
            "set_frost_protection",
            12.0,
        ),
        (
            "number.living_room_ac_overheat_protection_minimum_temperature",
            "set_overheat_protection",
            35.0,
        ),
        (
            "number.living_room_ac_overheat_protection_maximum_temperature",
            "set_overheat_protection",
            37.0,
        ),
        (
            "number.heat_pump_frost_protection_minimum_temperature",
            "set_frost_protection",
            5.0,
        ),
        (
            "number.heat_pump_frost_protection_maximum_temperature",
            "set_frost_protection",
            8.0,
        ),
        (
            "number.heat_pump_overheat_protection_minimum_temperature",
            "set_overheat_protection",
            40.0,
        ),
        (
            "number.heat_pump_overheat_protection_maximum_temperature",
            "set_overheat_protection",
            42.0,
        ),
    ],
)
@pytest.mark.parametrize(
    ("raise_exception", "expected_exception"),
    [
        (MelCloudHomeAuthenticationError, HomeAssistantError),
        (MelCloudHomeConnectionError, HomeAssistantError),
        (MelCloudHomeTimeoutError, HomeAssistantError),
    ],
)
async def test_set_value_exceptions(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    method: str,
    value: float,
    raise_exception: type[Exception],
    expected_exception: type[Exception],
) -> None:
    """Test number actions raise HomeAssistantError on client errors."""
    await setup_integration(hass, mock_config_entry)

    method_mock = getattr(mock_melcloud_client, method)
    method_mock.side_effect = raise_exception

    with pytest.raises(expected_exception):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
            blocking=True,
        )
