"""Test the eurotronic_cometblue sensor platform."""

from freezegun import freeze_time
import pytest
from syrupy.assertion import SnapshotAssertion
import voluptuous as vol

from homeassistant.components.eurotronic_cometblue import DOMAIN
from homeassistant.components.number import ServiceValidationError
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .conftest import setup_with_selected_platforms

from tests.common import MockConfigEntry

ENTITY_ID = "climate.comet_blue_aa_bb_cc_dd_ee_ff"


async def test_get_schedule(
    hass: HomeAssistant,
    # entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor entity state and registry data."""
    await setup_with_selected_platforms(hass, mock_config_entry)

    schedule = await hass.services.async_call(
        DOMAIN,
        "get_schedule",
        {"entity_id": ENTITY_ID},
        blocking=True,
        return_response=True,
    )

    snapshot.assert_match(schedule)


async def test_set_schedule(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor entity state and registry data."""
    await setup_with_selected_platforms(hass, mock_config_entry)

    # Only changed days should be updated, the rest remains the same.
    await hass.services.async_call(
        DOMAIN,
        "set_schedule",
        {
            "entity_id": ENTITY_ID,
            "monday": [{"from": "08:00", "to": "17:00"}],
            "sunday": [
                {"from": "09:00", "to": "11:30"},
                {"from": "13:00", "to": "15:00"},
                {"from": "18:00", "to": "22:00"},
                {"from": "23:00", "to": "23:40"},
            ],
        },
        blocking=True,
    )
    schedule = await hass.services.async_call(
        DOMAIN,
        "get_schedule",
        {"entity_id": ENTITY_ID},
        blocking=True,
        return_response=True,
    )
    assert schedule == snapshot(name="changed")

    await hass.services.async_call(
        DOMAIN,
        "set_schedule",
        {
            "entity_id": ENTITY_ID,
            "tuesday": [
                {"from": "18:00", "to": "22:00"},
                {"from": "09:00", "to": "11:30"},
                {"from": "23:00", "to": "23:40"},
                {"from": "13:00", "to": "15:00"},
            ],
        },
        blocking=True,
    )
    schedule = await hass.services.async_call(
        DOMAIN,
        "get_schedule",
        {"entity_id": ENTITY_ID},
        blocking=True,
        return_response=True,
    )
    assert schedule == snapshot(name="sorted")

    # Test deleting schedule from device
    await hass.services.async_call(
        DOMAIN,
        "set_schedule",
        {
            "entity_id": ENTITY_ID,
            "monday": [],
            "friday": [],
        },
        blocking=True,
    )
    schedule = await hass.services.async_call(
        DOMAIN,
        "get_schedule",
        {"entity_id": ENTITY_ID},
        blocking=True,
        return_response=True,
    )
    assert schedule == snapshot(name="deleted")


async def test_set_schedule_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor entity state and registry data."""
    await setup_with_selected_platforms(hass, mock_config_entry)

    # voloptuous schema should catch invalid time formats and incorrect data
    with pytest.raises(vol.Invalid, match="Invalid time specified"):
        await hass.services.async_call(
            DOMAIN,
            "set_schedule",
            {
                "entity_id": ENTITY_ID,
                "monday": [{"from": "08:00", "to": "24:01"}],
            },
            blocking=True,
        )

    with pytest.raises(vol.Invalid, match="expected a list for dictionary value"):
        await hass.services.async_call(
            DOMAIN,
            "set_schedule",
            {
                "entity_id": ENTITY_ID,
                "monday": {"from": "08:00", "to": "24:01"},
            },
            blocking=True,
        )

    with pytest.raises(vol.Invalid, match="expected a list for dictionary value"):
        await hass.services.async_call(
            DOMAIN,
            "set_schedule",
            {
                "entity_id": ENTITY_ID,
                "monday": "08:00-17:00",
            },
            blocking=True,
        )

    # Errors not caught by voluptous schema
    with pytest.raises(ServiceValidationError, match="Missing from/to in entry"):
        await hass.services.async_call(
            DOMAIN,
            "set_schedule",
            {
                "entity_id": ENTITY_ID,
                "monday": [{"from": "08:00"}],
            },
            blocking=True,
        )

    with pytest.raises(
        ServiceValidationError, match="maximum of 4 schedule entries is supported"
    ):
        await hass.services.async_call(
            DOMAIN,
            "set_schedule",
            {
                "entity_id": ENTITY_ID,
                "monday": [
                    {"from": "08:00", "to": "10:00"},
                    {"from": "10:00", "to": "12:00"},
                    {"from": "12:00", "to": "14:00"},
                    {"from": "14:00", "to": "16:00"},
                    {"from": "16:00", "to": "18:00"},
                ],
            },
            blocking=True,
        )

    with pytest.raises(
        ServiceValidationError, match="Overlapping times found in schedule"
    ):
        await hass.services.async_call(
            DOMAIN,
            "set_schedule",
            {
                "entity_id": ENTITY_ID,
                "monday": [
                    {"from": "12:00", "to": "14:00"},
                    {"from": "10:00", "to": "16:00"},
                ],
            },
            blocking=True,
        )

    with pytest.raises(ServiceValidationError, match="Invalid time range"):
        await hass.services.async_call(
            DOMAIN,
            "set_schedule",
            {
                "entity_id": ENTITY_ID,
                "monday": [{"from": "08:00", "to": "07:00"}],
            },
            blocking=True,
        )


@freeze_time("2026-04-01T18:03:00+00:00")
async def test_set_holiday(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor entity state and registry data."""
    await setup_with_selected_platforms(hass, mock_config_entry)

    # Only changed days should be updated, the rest remains the same.
    await hass.services.async_call(
        DOMAIN,
        "set_holiday",
        {
            "entity_id": ENTITY_ID,
            "from": "2026-04-01 19:00:00",
            "to": "2026-04-10 12:30:00",
            "temperature": 21.5,
        },
        blocking=True,
    )
    await mock_config_entry.runtime_data.async_refresh()

    # Testing against device data as holiday is not directly exposed as entity state
    # Datetime is also floored to hours in local time
    assert mock_config_entry.runtime_data.data.holiday == {
        "start": dt_util.dt.datetime(2026, 4, 1, 19, 0, 0),
        "end": dt_util.dt.datetime(2026, 4, 10, 12, 0, 0),
        "temperature": 21.5,
    }


@freeze_time("2026-04-01T18:03:00+00:00")
async def test_set_holiday_errors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor entity state and registry data."""
    await setup_with_selected_platforms(hass, mock_config_entry)

    # Start date must be in the future (at least 1 hour ahead as time is floored to hours on device)
    with pytest.raises(
        ServiceValidationError, match="Start date .* must be in the future"
    ):
        await hass.services.async_call(
            DOMAIN,
            "set_holiday",
            {
                "entity_id": ENTITY_ID,
                "from": "2026-04-01 17:50:00",
                "to": "2026-04-10 12:30:00",
                "temperature": 21.5,
            },
            blocking=True,
        )

    # Temperature must be a half precision float
    with pytest.raises(
        ServiceValidationError, match="value .* is not a half precision float"
    ):
        await hass.services.async_call(
            DOMAIN,
            "set_holiday",
            {
                "entity_id": ENTITY_ID,
                "from": "2026-04-01 19:00:00",
                "to": "2026-04-10 12:30:00",
                "temperature": 21.3,
            },
            blocking=True,
        )
