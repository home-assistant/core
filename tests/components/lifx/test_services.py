"""Tests for the LIFX services."""

from unittest.mock import patch

from lifx import LifxTimeoutError
import pytest

from homeassistant.components.lifx import DOMAIN
from homeassistant.components.lifx.const import (
    CONF_SERIAL,
    SERVICE_EFFECT_COLORLOOP,
    SERVICE_EFFECT_FLAME,
    SERVICE_EFFECT_MORPH,
    SERVICE_EFFECT_MOVE,
    SERVICE_EFFECT_PULSE,
    SERVICE_EFFECT_SKY,
    SERVICE_EFFECT_STOP,
    SERVICE_PAINT_THEME,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component

from . import IP_ADDRESS, SERIAL
from .helpers import create_mock_hev_light

from tests.common import MockConfigEntry

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
    """Test all actions are registered during component setup."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    for service in (*SERVICES, "set_state", "set_hev_cycle_state"):
        assert hass.services.has_service(DOMAIN, service)


@pytest.mark.parametrize("service", SERVICES)
@pytest.mark.usefixtures("mock_discovery")
async def test_service_without_loaded_entry_raises(
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


@pytest.mark.parametrize("service", ["set_state", "set_hev_cycle_state"])
@pytest.mark.usefixtures("mock_discovery")
async def test_entity_action_does_not_control_device_after_failed_setup(
    hass: HomeAssistant, service: str
) -> None:
    """Test registered entity actions cannot command a device that failed setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data={CONF_HOST: IP_ADDRESS, CONF_SERIAL: SERIAL},
        unique_id=SERIAL,
    )
    entry.add_to_hass(hass)
    device = create_mock_hev_light()
    device.refresh_state.side_effect = LifxTimeoutError("timed out")
    with patch("homeassistant.components.lifx.Device.connect", return_value=device):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert hass.services.has_service(DOMAIN, service)

    await hass.services.async_call(
        DOMAIN,
        service,
        {ATTR_ENTITY_ID: "light.my_group_my_bulb", "power": True},
        blocking=True,
    )

    device.set_power.assert_not_called()
    device.set_color.assert_not_called()
    device.set_hev_cycle.assert_not_called()
