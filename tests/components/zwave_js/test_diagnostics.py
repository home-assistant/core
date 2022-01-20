"""Test the Z-Wave JS diagnostics."""
from unittest.mock import patch

import pytest

from homeassistant.components.zwave_js.diagnostics import async_get_device_diagnostics
from homeassistant.components.zwave_js.helpers import get_device_id
from homeassistant.helpers.device_registry import async_get

from tests.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)


async def test_config_entry_diagnostics(hass, hass_client, integration):
    """Test the config entry level diagnostics data dump."""
    with patch(
        "homeassistant.components.zwave_js.diagnostics.dump_msgs",
        return_value=[{"hello": "world"}, {"second": "msg"}],
    ):
        assert await get_diagnostics_for_config_entry(
            hass, hass_client, integration
        ) == [{"hello": "world"}, {"second": "msg"}]


async def test_device_diagnostics(
    hass,
    client,
    aeon_smart_switch_6,
    aeon_smart_switch_6_state,
    integration,
    hass_client,
):
    """Test the device level diagnostics data dump."""
    dev_reg = async_get(hass)
    device = dev_reg.async_get_device({get_device_id(client, aeon_smart_switch_6)})
    assert device
    assert (
        await get_diagnostics_for_device(hass, hass_client, integration, device)
        == aeon_smart_switch_6_state
    )


async def test_device_diagnostics_error(hass, integration):
    """Test the device diagnostics raises exception when an invalid device is used."""
    dev_reg = async_get(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id=integration.entry_id, identifiers={("test", "test")}
    )
    with pytest.raises(ValueError):
        await async_get_device_diagnostics(hass, integration, device)
