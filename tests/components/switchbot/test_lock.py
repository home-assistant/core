"""Test the switchbot locks."""

from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_LOCK,
    SERVICE_OPEN,
    SERVICE_UNLOCK,
)
from homeassistant.core import HomeAssistant

from . import LOCK_SERVICE_INFO, WOLOCKPRO_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.parametrize(
    ("sensor_type", "service_info"),
    [("lock_pro", WOLOCKPRO_SERVICE_INFO), ("lock", LOCK_SERVICE_INFO)],
)
@pytest.mark.parametrize(
    ("service", "mock_method"),
    [(SERVICE_UNLOCK, "unlock"), (SERVICE_LOCK, "lock")],
)
async def test_lock_services(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
    sensor_type: str,
    service: str,
    mock_method: str,
    service_info: BluetoothServiceInfoBleak,
) -> None:
    """Test lock and unlock services on lock and lockpro devices."""
    inject_bluetooth_service_info(hass, service_info)

    entry = mock_entry_encrypted_factory(sensor_type=sensor_type)
    entry.add_to_hass(hass)

    with patch(
        f"homeassistant.components.switchbot.lock.switchbot.SwitchbotLock.{mock_method}",
    ) as mocked_instance:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "lock.test_name"

        await hass.services.async_call(
            LOCK_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

        mocked_instance.assert_awaited_once()


@pytest.mark.parametrize(
    ("sensor_type", "service_info"),
    [("lock_pro", WOLOCKPRO_SERVICE_INFO), ("lock", LOCK_SERVICE_INFO)],
)
@pytest.mark.parametrize(
    ("service", "mock_method"),
    [(SERVICE_UNLOCK, "unlock_without_unlatch"), (SERVICE_OPEN, "unlock")],
)
async def test_lock_services_with_night_latch_enabled(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
    sensor_type: str,
    service: str,
    mock_method: str,
    service_info: BluetoothServiceInfoBleak,
) -> None:
    """Test lock service when night latch enabled."""
    inject_bluetooth_service_info(hass, service_info)

    entry = mock_entry_encrypted_factory(sensor_type=sensor_type)
    entry.add_to_hass(hass)

    mocked_instance = AsyncMock(return_value=True)

    with patch.multiple(
        "homeassistant.components.switchbot.lock.switchbot.SwitchbotLock",
        is_night_latch_enabled=MagicMock(return_value=True),
        **{mock_method: mocked_instance},
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "lock.test_name"

        await hass.services.async_call(
            LOCK_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

        mocked_instance.assert_awaited_once()
