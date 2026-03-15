"""Tests for the TRMNL time platform."""

from datetime import time
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.time import (
    ATTR_TIME,
    DOMAIN as TIME_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_trmnl_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all time entities."""
    with patch("homeassistant.components.trmnl.PLATFORMS", [Platform.TIME]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "new_value", "expected_kwargs"),
    [
        (
            "time.test_trmnl_sleep_start_time",
            time(22, 0),
            {"sleep_start_time": 1320},
        ),
        (
            "time.test_trmnl_sleep_end_time",
            time(8, 0),
            {"sleep_end_time": 480},
        ),
    ],
)
async def test_set_value(
    hass: HomeAssistant,
    mock_trmnl_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    new_value: time,
    expected_kwargs: dict[str, int],
) -> None:
    """Test setting a time value calls the client and triggers a coordinator refresh."""
    with patch("homeassistant.components.trmnl.PLATFORMS", [Platform.TIME]):
        await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TIME: new_value},
        blocking=True,
    )

    mock_trmnl_client.update_device.assert_called_once_with(42793, **expected_kwargs)
    assert mock_trmnl_client.get_devices.call_count == 2
