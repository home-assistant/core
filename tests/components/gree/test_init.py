"""Tests for the Gree Integration."""

from unittest.mock import AsyncMock, Mock, patch

from greeclimate.device import Device
from greeclimate.deviceinfo import DeviceInfo
import pytest

from homeassistant.components.climate import HVACMode
from homeassistant.components.gree.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import async_setup_gree

from tests.common import MockConfigEntry


async def test_setup_simple(hass: HomeAssistant) -> None:
    """Test gree integration is setup."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.gree.climate.async_setup_entry",
            return_value=True,
        ) as climate_setup,
        patch(
            "homeassistant.components.gree.switch.async_setup_entry",
            return_value=True,
        ) as switch_setup,
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        assert len(climate_setup.mock_calls) == 1
        assert len(switch_setup.mock_calls) == 1
        assert entry.state is ConfigEntryState.LOADED

    # No flows started
    assert len(hass.config_entries.flow.async_progress()) == 0


async def test_unload_config_entry(hass: HomeAssistant) -> None:
    """Test that the async_unload_entry works."""
    # As we have currently no configuration, we just to pass the domain here.
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("response_type", "columns_key", "values_key"),
    [
        pytest.param("dat", "cols", "dat", id="status"),
        pytest.param("res", "opt", "val", id="command-result"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entities_receive_device_state(
    hass: HomeAssistant,
    device: Mock,
    response_type: str,
    columns_key: str,
    values_key: str,
) -> None:
    """Test real device replies make entities available and update their state."""
    with patch.object(Device, "_handlers", {}):
        gree_device = Device(
            DeviceInfo("1.1.1.1", 7000, "aabbcc112233", "fake-device-1")
        )
        gree_device.bind = AsyncMock()
        gree_device.update_state = AsyncMock()
        gree_device.power = True
        gree_device.mode = 1
        gree_device.temperature_units = 0
        gree_device.light = False
        gree_device.quiet = False
        gree_device.fresh_air = False
        gree_device.xfan = False
        gree_device.anion = False
        device.return_value = gree_device
        await async_setup_gree(hass)
        expected_states = {
            "climate.fake_device_1": HVACMode.COOL,
            "switch.fake_device_1_panel_light": STATE_OFF,
            "switch.fake_device_1_quiet_mode": STATE_OFF,
            "switch.fake_device_1_fresh_air": STATE_OFF,
            "switch.fake_device_1_xtra_fan": STATE_OFF,
            "switch.fake_device_1_health_mode": STATE_OFF,
        }

        for entity_id in expected_states:
            state = hass.states.get(entity_id)
            assert state is not None
            assert state.state == STATE_UNAVAILABLE

        gree_device.packet_received(
            {
                "pack": {
                    "t": response_type,
                    columns_key: [
                        "Pow",
                        "Mod",
                        "TemUn",
                        "Lig",
                        "Quiet",
                        "Air",
                        "Blo",
                        "Health",
                    ],
                    values_key: [1, 1, 0, 0, 0, 0, 0, 0],
                }
            },
            ("1.1.1.1", 7000),
        )
        await hass.async_block_till_done()

        for entity_id, expected_state in expected_states.items():
            state = hass.states.get(entity_id)
            assert state is not None
            assert state.state == expected_state

        gree_device.packet_received(
            {
                "pack": {
                    "t": response_type,
                    columns_key: ["Pow", "Lig"],
                    values_key: [0, 1],
                }
            },
            ("1.1.1.1", 7000),
        )
        await hass.async_block_till_done()

        assert hass.states.get("climate.fake_device_1").state == HVACMode.OFF
        assert hass.states.get("switch.fake_device_1_panel_light").state == STATE_ON
