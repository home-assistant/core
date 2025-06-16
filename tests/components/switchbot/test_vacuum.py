"""Tests for switchbot vacuum."""

from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.vacuum import (
    DOMAIN as VACUUM_DOMAIN,
    SERVICE_RETURN_TO_BASE,
    SERVICE_START,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from . import (
    K10_POR_COMBO_VACUUM_SERVICE_INFO,
    K10_PRO_VACUUM_SERVICE_INFO,
    K10_VACUUM_SERVICE_INFO,
    K20_VACUUM_SERVICE_INFO,
    S10_VACUUM_SERVICE_INFO,
)

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.parametrize(
    ("sensor_type", "service_info"),
    [
        ("k20_vacuum", K20_VACUUM_SERVICE_INFO),
        ("s10_vacuum", S10_VACUUM_SERVICE_INFO),
        ("k10_pro_combo_vacumm", K10_POR_COMBO_VACUUM_SERVICE_INFO),
        ("k10_vacuum", K10_VACUUM_SERVICE_INFO),
        ("k10_pro_vacuum", K10_PRO_VACUUM_SERVICE_INFO),
    ],
)
@pytest.mark.parametrize(
    ("service", "mock_method"),
    [(SERVICE_START, "clean_up"), (SERVICE_RETURN_TO_BASE, "return_to_dock")],
)
async def test_vacuum_controlling(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
    sensor_type: str,
    service: str,
    mock_method: str,
    service_info: BluetoothServiceInfoBleak,
) -> None:
    """Test switchbot vacuum controlling."""

    inject_bluetooth_service_info(hass, service_info)

    entry = mock_entry_factory(sensor_type)
    entry.add_to_hass(hass)

    mocked_instance = AsyncMock(return_value=True)

    with patch.multiple(
        "homeassistant.components.switchbot.vacuum.switchbot.SwitchbotVacuum",
        update=MagicMock(return_value=None),
        **{mock_method: mocked_instance},
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "vacuum.test_name"

        await hass.services.async_call(
            VACUUM_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

        mocked_instance.assert_awaited_once()
