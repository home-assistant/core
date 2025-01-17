"""Test for the climate entities of Fujitsu HVAC."""

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_SWING_MODE,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_AUTO,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    SWING_BOTH,
    HVACMode,
)
from homeassistant.components.fujitsu_fglair.climate import (
    HA_TO_FUJI_FAN,
    HA_TO_FUJI_HVAC,
    HA_TO_FUJI_SWING,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import entity_id

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.CLIMATE]


async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_ayla_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test that coordinator returns the data we expect after the first refresh."""
    assert await integration_setup()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_set_attributes(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_ayla_api: AsyncMock,
    mock_devices: list[AsyncMock],
    mock_config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test that setting the attributes calls the correct functions on the device."""
    assert await integration_setup()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        service_data={ATTR_HVAC_MODE: HVACMode.COOL},
        target={ATTR_ENTITY_ID: entity_id(mock_devices[0])},
        blocking=True,
    )
    mock_devices[0].async_set_op_mode.assert_called_once_with(
        HA_TO_FUJI_HVAC[HVACMode.COOL]
    )

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        service_data={ATTR_FAN_MODE: FAN_AUTO},
        target={ATTR_ENTITY_ID: entity_id(mock_devices[0])},
        blocking=True,
    )
    mock_devices[0].async_set_fan_speed.assert_called_once_with(
        HA_TO_FUJI_FAN[FAN_AUTO]
    )

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_SWING_MODE,
        service_data={ATTR_SWING_MODE: SWING_BOTH},
        target={ATTR_ENTITY_ID: entity_id(mock_devices[0])},
        blocking=True,
    )
    mock_devices[0].async_set_swing_mode.assert_called_once_with(
        HA_TO_FUJI_SWING[SWING_BOTH]
    )

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        service_data={ATTR_TEMPERATURE: 23.0},
        target={ATTR_ENTITY_ID: entity_id(mock_devices[0])},
        blocking=True,
    )
    mock_devices[0].async_set_set_temp.assert_called_once_with(23.0)
