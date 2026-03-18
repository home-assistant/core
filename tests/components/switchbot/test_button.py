"""Tests for the switchbot button platform."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import ART_FRAME_INFO, DOMAIN, WOMETERTHPC_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.parametrize(
    ("service", "mock_method", "entity_id"),
    [
        (SERVICE_PRESS, "next_image", "button.test_name_next_image"),
        (SERVICE_PRESS, "prev_image", "button.test_name_previous_image"),
    ],
)
async def test_art_frame_button_press(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
    service: str,
    mock_method: str,
    entity_id: str,
) -> None:
    """Test pressing the button on the art frame device."""
    inject_bluetooth_service_info(hass, ART_FRAME_INFO)

    entry = mock_entry_encrypted_factory("art_frame")
    entry.add_to_hass(hass)

    mock_basic_info = AsyncMock(
        return_value=b"\x016\x07\x01\x00\x00\x04\x00\xde\x18\xa5\x00\x00\x00\x00\x00\x00"
    )
    mocked_instance = AsyncMock(return_value=True)
    with patch.multiple(
        "homeassistant.components.switchbot.button.switchbot.SwitchbotArtFrame",
        _get_basic_info=mock_basic_info,
        **{mock_method: mocked_instance},
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_ids = [
            entity.entity_id for entity in hass.states.async_all(BUTTON_DOMAIN)
        ]
        assert entity_ids, "No button entities found"

        await hass.services.async_call(
            BUTTON_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

        mocked_instance.assert_awaited_once()


async def test_meter_pro_co2_sync_datetime_button(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
) -> None:
    """Test pressing the sync datetime button on Meter Pro CO2."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WOMETERTHPC_SERVICE_INFO)

    entry = mock_entry_factory("hygrometer_co2")
    entry.add_to_hass(hass)

    mock_set_datetime = AsyncMock(return_value=True)

    # Use a fixed datetime for testing
    fixed_time = datetime(2025, 1, 9, 12, 30, 45, tzinfo=UTC)

    with (
        patch(
            "switchbot.SwitchbotMeterProCO2.set_datetime",
            mock_set_datetime,
        ),
        patch(
            "homeassistant.components.switchbot.button.dt_util.now",
            return_value=fixed_time,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_ids = [
            entity.entity_id for entity in hass.states.async_all(BUTTON_DOMAIN)
        ]
        assert "button.test_name_sync_date_and_time" in entity_ids

        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.test_name_sync_date_and_time"},
            blocking=True,
        )

        mock_set_datetime.assert_awaited_once_with(
            timestamp=int(fixed_time.timestamp()),
            utc_offset_hours=0,
            utc_offset_minutes=0,
        )


@pytest.mark.parametrize(
    ("tz", "expected_utc_offset_hours", "expected_utc_offset_minutes"),
    [
        (timezone(timedelta(hours=0, minutes=0)), 0, 0),
        (timezone(timedelta(hours=0, minutes=30)), 0, 30),
        (timezone(timedelta(hours=8, minutes=0)), 8, 0),
        (timezone(timedelta(hours=-5, minutes=30)), -5, 30),
        (timezone(timedelta(hours=5, minutes=30)), 5, 30),
        (timezone(timedelta(hours=-5, minutes=-30)), -6, 30),  # -6h + 30m = -5:30
        (timezone(timedelta(hours=-5, minutes=-45)), -6, 15),  # -6h + 15m = -5:45
    ],
)
async def test_meter_pro_co2_sync_datetime_button_with_timezone(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
    tz: timezone,
    expected_utc_offset_hours: int,
    expected_utc_offset_minutes: int,
) -> None:
    """Test sync datetime button with non-UTC timezone."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WOMETERTHPC_SERVICE_INFO)

    entry = mock_entry_factory("hygrometer_co2")
    entry.add_to_hass(hass)

    mock_set_datetime = AsyncMock(return_value=True)

    fixed_time = datetime(2025, 1, 9, 18, 0, 45, tzinfo=tz)

    with (
        patch(
            "switchbot.SwitchbotMeterProCO2.set_datetime",
            mock_set_datetime,
        ),
        patch(
            "homeassistant.components.switchbot.button.dt_util.now",
            return_value=fixed_time,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.test_name_sync_date_and_time"},
            blocking=True,
        )

        mock_set_datetime.assert_awaited_once_with(
            timestamp=int(fixed_time.timestamp()),
            utc_offset_hours=expected_utc_offset_hours,
            utc_offset_minutes=expected_utc_offset_minutes,
        )
