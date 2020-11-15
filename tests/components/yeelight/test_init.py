"""Test Yeelight."""
from homeassistant.components.yeelight import (
    CONF_NIGHTLIGHT_SWITCH_TYPE,
    DOMAIN,
    NIGHTLIGHT_SWITCH_TYPE_LIGHT,
)
from homeassistant.const import CONF_DEVICES, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import (
    CONFIG_ENTRY_DATA,
    IP_ADDRESS,
    MODULE,
    MODULE_CONFIG_FLOW,
    NAME,
    _mocked_bulb,
    _patch_discovery,
)

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_setup_discovery(hass: HomeAssistant):
    """Test setting up Yeelight by discovery."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=CONFIG_ENTRY_DATA)
    config_entry.add_to_hass(hass)

    mocked_bulb = _mocked_bulb()
    with _patch_discovery(MODULE), patch(f"{MODULE}.Bulb", return_value=mocked_bulb):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(f"binary_sensor.{NAME}_nightlight") is not None
    assert hass.states.get(f"light.{NAME}") is not None

    # Unload
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert hass.states.get(f"binary_sensor.{NAME}_nightlight") is None
    assert hass.states.get(f"light.{NAME}") is None


async def test_setup_import(hass: HomeAssistant):
    """Test import from yaml."""
    mocked_bulb = _mocked_bulb()
    name = "yeelight"
    with patch(f"{MODULE}.Bulb", return_value=mocked_bulb), patch(
        f"{MODULE_CONFIG_FLOW}.yeelight.Bulb", return_value=mocked_bulb
    ):
        assert await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: {
                    CONF_DEVICES: {
                        IP_ADDRESS: {
                            CONF_NAME: name,
                            CONF_NIGHTLIGHT_SWITCH_TYPE: NIGHTLIGHT_SWITCH_TYPE_LIGHT,
                        }
                    }
                }
            },
        )
        await hass.async_block_till_done()

    assert hass.states.get(f"binary_sensor.{name}_nightlight") is not None
    assert hass.states.get(f"light.{name}") is not None
    assert hass.states.get(f"light.{name}_nightlight") is not None
