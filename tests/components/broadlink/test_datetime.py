"""Tests for Broadlink datetime."""

from homeassistant.components.broadlink.const import DOMAIN
from homeassistant.components.datetime import (
    ATTR_DATETIME,
    DOMAIN as DATETIME_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import get_device


async def test_datetime(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Broadlink datetime."""
    hass.config.set_time_zone("UTC")

    device = get_device("Guest room")
    mock_setup = await device.setup_entry(hass)

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_setup.entry.unique_id)}
    )
    entries = er.async_entries_for_device(entity_registry, device_entry.id)
    datetimes = [entry for entry in entries if entry.domain == Platform.DATETIME]
    assert len(datetimes) == 1

    datetime = datetimes[0]

    # set value
    await hass.services.async_call(
        DATETIME_DOMAIN,
        SERVICE_SET_VALUE,
        {"entity_id": datetime.entity_id, ATTR_DATETIME: "2024-04-30T03:04:05+00:00"},
        blocking=True,
    )
    state = hass.states.get(datetime.entity_id)
    assert state.state == "2024-04-30T03:04:05+00:00"
    assert mock_setup.api.set_time.call_count == 1
    assert mock_setup.api.set_time.call_args.kwargs["hour"] == 3
    assert mock_setup.api.set_time.call_args.kwargs["minute"] == 4
    assert mock_setup.api.set_time.call_args.kwargs["second"] == 5
    assert mock_setup.api.set_time.call_args.kwargs["day"] == 2
