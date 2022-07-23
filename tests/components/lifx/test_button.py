"""Tests for button platform."""
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
    assert entity.disabled
    assert entity.unique_id == unique_id

    enabled_entity = entity_registry.async_update_entity(entity_id, disabled_by=None)
    assert not enabled_entity.disabled

    with _patch_discovery(device=bulb), _patch_config_flow_try_connect(
        device=bulb
    ), _patch_device(device=bulb):
        await hass.config_entries.async_reload(config_entry.entry_id)
        await hass.async_block_till_done()

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
    assert entity.disabled
    assert entity.unique_id == unique_id

    enabled_entity = entity_registry.async_update_entity(entity_id, disabled_by=None)
    assert not enabled_entity.disabled

    with _patch_discovery(device=bulb), _patch_config_flow_try_connect(
        device=bulb
    ), _patch_device(device=bulb):
        await hass.config_entries.async_reload(config_entry.entry_id)
        await hass.async_block_till_done()

    await hass.services.async_call(
        BUTTON_DOMAIN, "press", {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    call_dict = bulb.set_waveform_optional.calls[0][1]
    call_dict.pop("callb")
    assert call_dict == {
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
