"""Tests for Daikin services."""

from unittest.mock import AsyncMock

import pytest
import voluptuous as vol

from homeassistant.components.daikin.const import DOMAIN, KEY_MAC
from homeassistant.components.daikin.services import ATTR_EN_DEMAND, ATTR_MAX_POW
from homeassistant.const import ATTR_DEVICE_ID, ATTR_MODE, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .conftest import ZoneDevice

from tests.common import MockConfigEntry

HOST = "127.0.0.1"


async def _async_setup_daikin(
    hass: HomeAssistant, zone_device: ZoneDevice
) -> MockConfigEntry:
    """Set up a Daikin config entry with a mocked library device."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=zone_device.mac,
        data={CONF_HOST: HOST, KEY_MAC: zone_device.mac},
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return config_entry


def _device_id(
    device_registry: dr.DeviceRegistry, config_entry_id: str, mac: str
) -> str:
    """Return the device id for a Daikin device."""
    return device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, mac), config_entry_id
    ).id


async def test_set_demand_control(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    zone_device: ZoneDevice,
) -> None:
    """Test the set_demand_control service."""
    zone_device.support_demand_control = True
    zone_device.set_demand_control = AsyncMock()

    config_entry = await _async_setup_daikin(hass, zone_device)

    await hass.services.async_call(
        DOMAIN,
        "set_demand_control",
        {
            ATTR_DEVICE_ID: _device_id(
                device_registry, config_entry.entry_id, zone_device.mac
            ),
            ATTR_EN_DEMAND: True,
            ATTR_MAX_POW: 40,
        },
        blocking=True,
    )

    zone_device.set_demand_control.assert_called_once_with(
        en_demand="on", max_pow=40, mode=0
    )


@pytest.mark.parametrize(
    ("mode", "expected_mode"),
    [
        ("manual", 0),
        ("scheduled", 1),
        ("auto", 2),
    ],
)
async def test_set_demand_control_with_mode(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    zone_device: ZoneDevice,
    mode: str,
    expected_mode: int,
) -> None:
    """Test the set_demand_control service with an explicit mode."""
    zone_device.support_demand_control = True
    zone_device.set_demand_control = AsyncMock()

    config_entry = await _async_setup_daikin(hass, zone_device)

    await hass.services.async_call(
        DOMAIN,
        "set_demand_control",
        {
            ATTR_DEVICE_ID: _device_id(
                device_registry, config_entry.entry_id, zone_device.mac
            ),
            ATTR_EN_DEMAND: True,
            ATTR_MAX_POW: 40,
            ATTR_MODE: mode,
        },
        blocking=True,
    )

    zone_device.set_demand_control.assert_called_once_with(
        en_demand="on", max_pow=40, mode=expected_mode
    )


async def test_set_demand_control_disabled(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    zone_device: ZoneDevice,
) -> None:
    """Test the set_demand_control service with demand control disabled.

    Disabling demand control does not require a maximum power value.
    """
    zone_device.support_demand_control = True
    zone_device.set_demand_control = AsyncMock()

    config_entry = await _async_setup_daikin(hass, zone_device)

    await hass.services.async_call(
        DOMAIN,
        "set_demand_control",
        {
            ATTR_DEVICE_ID: _device_id(
                device_registry, config_entry.entry_id, zone_device.mac
            ),
            ATTR_EN_DEMAND: False,
        },
        blocking=True,
    )

    zone_device.set_demand_control.assert_called_once_with(
        en_demand="off", max_pow=100, mode=0
    )


@pytest.mark.parametrize("invalid_max_pow", [0, 39, 101])
async def test_set_demand_control_invalid_max_pow(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    zone_device: ZoneDevice,
    invalid_max_pow: int,
) -> None:
    """Test that an out-of-range maximum power value is rejected."""
    zone_device.support_demand_control = True
    zone_device.set_demand_control = AsyncMock()

    config_entry = await _async_setup_daikin(hass, zone_device)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "set_demand_control",
            {
                ATTR_DEVICE_ID: _device_id(
                    device_registry, config_entry.entry_id, zone_device.mac
                ),
                ATTR_EN_DEMAND: True,
                ATTR_MAX_POW: invalid_max_pow,
            },
            blocking=True,
        )

    zone_device.set_demand_control.assert_not_called()


async def test_set_demand_control_unsupported(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    zone_device: ZoneDevice,
) -> None:
    """Test the set_demand_control service on a device that does not support it."""
    zone_device.support_demand_control = False

    config_entry = await _async_setup_daikin(hass, zone_device)

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN,
            "set_demand_control",
            {
                ATTR_DEVICE_ID: _device_id(
                    device_registry, config_entry.entry_id, zone_device.mac
                ),
                ATTR_EN_DEMAND: True,
                ATTR_MAX_POW: 40,
            },
            blocking=True,
        )
    assert err.value.translation_key == "demand_control_unsupported"
