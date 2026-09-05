"""Tests for the LIFX services."""

import pytest

from homeassistant.components.lifx import DOMAIN
from homeassistant.components.lifx.const import (
    DATA_LIFX_MANAGER,
    SERVICE_EFFECT_COLORLOOP,
    SERVICE_EFFECT_FLAME,
    SERVICE_EFFECT_MORPH,
    SERVICE_EFFECT_MOVE,
    SERVICE_EFFECT_PULSE,
    SERVICE_EFFECT_SKY,
    SERVICE_EFFECT_STOP,
    SERVICE_PAINT_THEME,
)
from homeassistant.components.lifx.manager import LIFXManager
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component

SERVICES = (
    SERVICE_EFFECT_COLORLOOP,
    SERVICE_EFFECT_FLAME,
    SERVICE_EFFECT_MORPH,
    SERVICE_EFFECT_MOVE,
    SERVICE_EFFECT_PULSE,
    SERVICE_EFFECT_SKY,
    SERVICE_EFFECT_STOP,
    SERVICE_PAINT_THEME,
)


@pytest.mark.usefixtures("mock_discovery")
async def test_services_registered_without_entry(hass: HomeAssistant) -> None:
    """Test the effect actions are registered during component setup."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    for service in SERVICES:
        assert hass.services.has_service(DOMAIN, service)


@pytest.mark.parametrize("service", SERVICES)
@pytest.mark.usefixtures("mock_discovery")
async def test_service_without_manager_raises(
    hass: HomeAssistant, service: str
) -> None:
    """Test the effect actions raise when no config entry is loaded."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, service, {ATTR_ENTITY_ID: "light.test"}, blocking=True
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "not_loaded"
    assert "LIFX is not loaded" in str(err.value)


@pytest.mark.parametrize("service", SERVICES)
@pytest.mark.usefixtures("mock_discovery")
async def test_service_with_manager_but_no_loaded_entry_raises(
    hass: HomeAssistant, service: str
) -> None:
    """Test the actions raise when a failed setup left a manager behind.

    async_setup_entry stores the manager before awaiting the connection and the
    first refresh, so a setup retry leaves an empty manager in hass.data.
    """
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    # Simulate the leftover manager from a setup that raised ConfigEntryNotReady.
    hass.data[DATA_LIFX_MANAGER] = LIFXManager(hass)
    assert not hass.config_entries.async_loaded_entries(DOMAIN)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, service, {ATTR_ENTITY_ID: "light.test"}, blocking=True
        )

    assert err.value.translation_key == "not_loaded"
