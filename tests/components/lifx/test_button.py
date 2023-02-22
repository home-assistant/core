"""Tests for button platform."""
from unittest.mock import patch

import pytest

from homeassistant.components import lifx
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.lifx.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import (
    DEFAULT_ENTRY_TITLE,
    IP_ADDRESS,
    MAC_ADDRESS,
    SERIAL,
    _mocked_bulb,
    _patch_config_flow_try_connect,
    _patch_device,
    _patch_discovery,
)

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_lifx_coordinator_sleep():
    """Mock out lifx coordinator sleeps."""
    with patch("homeassistant.components.lifx.coordinator.LIFX_IDENTIFY_DELAY", 0):
        yield


async def test_button_restart(hass: HomeAssistant) -> None:
    """Test that a bulb can be restarted."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_ENTRY_TITLE,
        data={CONF_HOST: IP_ADDRESS},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    with _patch_discovery(device=bulb), _patch_config_flow_try_connect(
        device=bulb
    ), _patch_device(device=bulb):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    unique_id = f"{SERIAL}_restart"
    entity_id = "button.my_bulb_restart"

    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert not entity.disabled
    assert entity.unique_id == unique_id

    await hass.services.async_call(
        BUTTON_DOMAIN, "press", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    bulb.set_reboot.assert_called_once()


async def test_button_identify(hass: HomeAssistant) -> None:
    """Test that a bulb can be identified."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_ENTRY_TITLE,
        data={CONF_HOST: IP_ADDRESS},
        unique_id=MAC_ADDRESS,
    )
    config_entry.add_to_hass(hass)
    bulb = _mocked_bulb()
    with _patch_discovery(device=bulb), _patch_config_flow_try_connect(
        device=bulb
    ), _patch_device(device=bulb):
        await async_setup_component(hass, lifx.DOMAIN, {lifx.DOMAIN: {}})
        await hass.async_block_till_done()

    unique_id = f"{SERIAL}_identify"
    entity_id = "button.my_bulb_identify"

    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert not entity.disabled
    assert entity.unique_id == unique_id

    await hass.services.async_call(
        BUTTON_DOMAIN, "press", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    assert len(bulb.set_power.calls) == 2

    waveform_call_dict = bulb.set_waveform_optional.calls[0][1]
    waveform_call_dict.pop("callb")
    assert waveform_call_dict == {
        "rapid": False,
        "value": {
            "transient": True,
            "color": [0, 0, 1, 3500],
            "skew_ratio": 0,
            "period": 1000,
            "cycles": 3,
            "waveform": 1,
            "set_hue": True,
            "set_saturation": True,
            "set_brightness": True,
            "set_kelvin": True,
        },
    }

    bulb.set_power.reset_mock()
    bulb.set_waveform_optional.reset_mock()
    bulb.power_level = 65535

    await hass.services.async_call(
        BUTTON_DOMAIN, "press", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    assert len(bulb.set_waveform_optional.calls) == 1
    assert len(bulb.set_power.calls) == 0
