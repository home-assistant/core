"""Tests for Broadlink datetime."""

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.broadlink.const import DOMAIN
from homeassistant.components.datetime import (
    ATTR_DATETIME,
    DOMAIN as DATETIME_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from . import get_device


async def test_datetime(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Broadlink datetime."""
    await hass.config.async_set_time_zone("UTC")

    device = get_device("Guest room")
    mock_setup = await device.setup_entry(hass)

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_setup.entry.unique_id)}
    )
    entries = er.async_entries_for_device(entity_registry, device_entry.id)
    datetimes = [entry for entry in entries if entry.domain == Platform.DATETIME]
    assert len(datetimes) == 1

    datetime = datetimes[0]

    mock_setup.api.get_full_status.return_value = {
        "dayofweek": 3,
        "hour": 2,
        "min": 3,
        "sec": 4,
    }
    freezer.move_to("2024-04-30 12:00:00+00:00")
    await async_update_entity(hass, datetime.entity_id)
    assert mock_setup.api.get_full_status.call_count == 2
    state = hass.states.get(datetime.entity_id)
    assert state.state == "2024-04-24T02:03:04+00:00"

    # set value
    await hass.services.async_call(
        DATETIME_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: datetime.entity_id,
            ATTR_DATETIME: "2024-04-30T03:04:05+00:00",
        },
        blocking=True,
    )
    state = hass.states.get(datetime.entity_id)
    assert state.state == "2024-04-30T03:04:05+00:00"
    assert mock_setup.api.set_time.call_count == 1
    call_args = mock_setup.api.set_time.call_args.kwargs
    assert call_args == {
        "hour": 3,
        "minute": 4,
        "second": 5,
        "day": 2,
    }
