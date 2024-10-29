"""Tests for Broadlink select."""

from homeassistant.components.broadlink.const import DOMAIN
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity

from . import get_device


async def test_select(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test Broadlink select."""
    await hass.config.async_set_time_zone("UTC")

    device = get_device("Guest room")
    mock_setup = await device.setup_entry(hass)

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_setup.entry.unique_id)}
    )
    entries = er.async_entries_for_device(entity_registry, device_entry.id)
    selects = [entry for entry in entries if entry.domain == Platform.SELECT]
    assert len(selects) == 1

    select = selects[0]

    mock_setup.api.get_full_status.return_value = {
        "dayofweek": 3,
        "hour": 2,
        "min": 3,
        "sec": 4,
    }
    await async_update_entity(hass, select.entity_id)
    assert mock_setup.api.get_full_status.call_count == 2
    state = hass.states.get(select.entity_id)
    assert state.state == "wednesday"

    # set value
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: select.entity_id,
            ATTR_OPTION: "tuesday",
        },
        blocking=True,
    )
    state = hass.states.get(select.entity_id)
    assert state.state == "tuesday"
    assert mock_setup.api.set_time.call_count == 1
    call_args = mock_setup.api.set_time.call_args.kwargs
    assert call_args == {
        "hour": 2,
        "minute": 3,
        "second": 4,
        "day": 2,
    }
