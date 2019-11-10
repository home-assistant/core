"""Vera tests."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import async_get_registry

from .common import (
    DEVICE_IGNORE,
    RESPONSE_LU_SDATA_EMPTY,
    RESPONSE_SDATA,
    RESPONSE_STATUS,
    async_configure_component,
    get_device,
    get_entity_id,
)


async def test_ignore(hass: HomeAssistant) -> None:
    """Test function."""
    component_data = await async_configure_component(
        hass=hass,
        response_sdata=RESPONSE_SDATA,
        response_status=RESPONSE_STATUS,
        respone_lu_sdata=RESPONSE_LU_SDATA_EMPTY,
    )

    registry = await async_get_registry(hass)

    # Ignore device.
    ignore_device = get_device(DEVICE_IGNORE, component_data)
    entry = registry.async_get(get_entity_id(ignore_device, "switch"))
    assert entry is None
