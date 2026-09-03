"""Tests for the Modbus services."""

import pytest

from homeassistant.components.modbus.const import (
    ATTR_ADDRESS,
    ATTR_HUB,
    ATTR_VALUE,
    DATA_MODBUS_HUBS,
    DEFAULT_HUB,
    DOMAIN,
    SERVICE_STOP,
    SERVICE_WRITE_COIL,
    SERVICE_WRITE_REGISTER,
)
from homeassistant.const import ATTR_STATE, SERVICE_RELOAD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component

SERVICES = (
    SERVICE_WRITE_REGISTER,
    SERVICE_WRITE_COIL,
    SERVICE_STOP,
    SERVICE_RELOAD,
)


async def test_services_registered(hass: HomeAssistant) -> None:
    """Test the actions are registered during component setup."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: []})
    await hass.async_block_till_done()

    for service in SERVICES:
        assert hass.services.has_service(DOMAIN, service)


@pytest.mark.parametrize(
    ("service", "data"),
    [
        pytest.param(
            SERVICE_WRITE_REGISTER,
            {ATTR_HUB: DEFAULT_HUB, ATTR_ADDRESS: 1, ATTR_VALUE: 1},
            id="write_register",
        ),
        pytest.param(
            SERVICE_WRITE_COIL,
            {ATTR_HUB: DEFAULT_HUB, ATTR_ADDRESS: 1, ATTR_STATE: True},
            id="write_coil",
        ),
        pytest.param(SERVICE_STOP, {ATTR_HUB: DEFAULT_HUB}, id="stop"),
    ],
)
async def test_service_without_hubs_raises(
    hass: HomeAssistant, service: str, data: dict
) -> None:
    """Test the actions raise a user-facing error when Modbus is not set up."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: []})
    await hass.async_block_till_done()
    hass.data.pop(DATA_MODBUS_HUBS)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(DOMAIN, service, data, blocking=True)

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "not_loaded"
    assert "Modbus is not loaded" in str(err.value)
