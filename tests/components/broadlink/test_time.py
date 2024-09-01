"""Tests for Broadlink time."""

from homeassistant.components.broadlink.const import DOMAIN
from homeassistant.components.time import (
    ATTR_TIME,
    DOMAIN as TIME_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from . import get_device


async def test_time(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Broadlink time."""
    await hass.config.async_set_time_zone("UTC")

    device = get_device("Guest room")
    mock_setup = await device.setup_entry(hass)

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_setup.entry.unique_id)}
    )
    entries = er.async_entries_for_device(entity_registry, device_entry.id)
    times = [entry for entry in entries if entry.domain == Platform.TIME]
    assert len(times) == 1

    time = times[0]

    mock_setup.api.get_full_status.return_value = {
        "dayofweek": 3,
        "hour": 2,
        "min": 3,
        "sec": 4,
    }
    await async_update_entity(hass, time.entity_id)
    assert mock_setup.api.get_full_status.call_count == 2
    state = hass.states.get(time.entity_id)
    assert state.state == "02:03:04+00:00"

    # set value
    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: time.entity_id,
            ATTR_TIME: "03:04:05",
        },
        blocking=True,
    )
    state = hass.states.get(time.entity_id)
    assert state.state == "03:04:05"
    assert mock_setup.api.set_time.call_count == 1
    call_args = mock_setup.api.set_time.call_args.kwargs
    assert call_args == {
        "hour": 3,
        "minute": 4,
        "second": 5,
        "day": 3,
    }
