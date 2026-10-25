"""Tests for AVM Fritz!Box services."""

import re
from unittest.mock import Mock

from probatio import MultipleInvalid
import pytest

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.fritzbox.const import DOMAIN
from homeassistant.components.fritzbox.services import (
    ATTR_DURATION,
    SERVICE_SET_WINDOW_CLOSE,
    SERVICE_SET_WINDOW_OPEN,
)
from homeassistant.const import ATTR_DEVICE_ID, CONF_DEVICES
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import FritzDeviceClimateMock, setup_config_entry
from .const import CONF_FAKE_NAME, MOCK_CONFIG

ENTITY_ID = f"{CLIMATE_DOMAIN}.{CONF_FAKE_NAME}"


@pytest.mark.parametrize(
    "service_data",
    [
        {ATTR_DURATION: 1},
        {ATTR_DURATION: 30},
        {ATTR_DURATION: 86400},
    ],
)
async def test_set_window_open_good(
    hass: HomeAssistant,
    fritz: Mock,
    device_registry: dr.DeviceRegistry,
    service_data: dict[str, int],
) -> None:
    """Test set_window_open action with valid durations."""
    device = FritzDeviceClimateMock()

    ENTITY_ID = f"{CLIMATE_DOMAIN}.{CONF_FAKE_NAME}"
    entry = await setup_config_entry(
        hass, MOCK_CONFIG[DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )
    assert entry
    assert fritz().update_devices.call_count == 1

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, device.ain), entry.entry_id
    )
    assert device_entry

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_WINDOW_OPEN,
        {ATTR_DEVICE_ID: device_entry.id, **service_data},
        True,
    )
    assert fritz().set_window_open.call_count == 1
    assert fritz().set_window_open.call_args.args == (
        device.ain,
        service_data[ATTR_DURATION],
        True,
    )


@pytest.mark.parametrize(
    "service_data",
    [
        (
            {ATTR_DURATION: 0},
            re.escape("value must be at least 1 at 'duration'"),
        ),
        (
            {ATTR_DURATION: 86401},
            re.escape("value must be at most 86400 at 'duration'"),
        ),
    ],
)
async def test_set_window_open_bad(
    hass: HomeAssistant,
    fritz: Mock,
    device_registry: dr.DeviceRegistry,
    service_data: tuple[dict[str, int], str],
) -> None:
    """Test set_window_open action with invalid durations."""
    device = FritzDeviceClimateMock()

    entry = await setup_config_entry(
        hass, MOCK_CONFIG[DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )
    assert entry
    assert fritz().update_devices.call_count == 1

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, device.ain), entry.entry_id
    )
    assert device_entry

    with pytest.raises(MultipleInvalid, match=service_data[1]):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_WINDOW_OPEN,
            {ATTR_DEVICE_ID: device_entry.id, **service_data[0]},
            True,
        )

    assert fritz().set_window_open.call_count == 0


async def test_set_window_close(
    hass: HomeAssistant, fritz: Mock, device_registry: dr.DeviceRegistry
) -> None:
    """Test set_window_close action."""
    device = FritzDeviceClimateMock()

    entry = await setup_config_entry(
        hass, MOCK_CONFIG[DOMAIN][CONF_DEVICES][0], ENTITY_ID, device, fritz
    )
    assert entry
    assert fritz().update_devices.call_count == 1

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, device.ain), entry.entry_id
    )
    assert device_entry

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_WINDOW_CLOSE,
        {ATTR_DEVICE_ID: device_entry.id},
        True,
    )

    assert fritz().set_window_open.call_count == 1
    assert fritz().set_window_open.call_args.args == (
        device.ain,
        0,
        True,
    )
