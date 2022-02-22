"""Test the Z-Wave JS diagnostics."""
from unittest.mock import patch

import pytest
from zwave_js_server.event import Event

from homeassistant.components.zwave_js.diagnostics import async_get_device_diagnostics
from homeassistant.components.zwave_js.helpers import get_device_id
from homeassistant.helpers.device_registry import async_get

from .common import PROPERTY_ULTRAVIOLET

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
    multisensor_6,
    integration,
    hass_client,
    version_state,
):
    """Test the device level diagnostics data dump."""
    dev_reg = async_get(hass)
    device = dev_reg.async_get_device({get_device_id(client, multisensor_6)})
    assert device

    # Update a value and ensure it is reflected in the node state
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": multisensor_6.node_id,
            "args": {
                "commandClassName": "Multilevel Sensor",
                "commandClass": 49,
                "endpoint": 0,
                "property": PROPERTY_ULTRAVIOLET,
                "newValue": 1,
                "prevValue": 0,
                "propertyName": PROPERTY_ULTRAVIOLET,
            },
        },
    )
    multisensor_6.receive_event(event)

    diagnostics_data = await get_diagnostics_for_device(
        hass, hass_client, integration, device
    )
    assert diagnostics_data["versionInfo"] == {
        "driverVersion": version_state["driverVersion"],
        "serverVersion": version_state["serverVersion"],
        "minSchemaVersion": 0,
        "maxSchemaVersion": 0,
    }

    assert diagnostics_data["state"] == multisensor_6.data


async def test_device_diagnostics_error(hass, integration):
    """Test the device diagnostics raises exception when an invalid device is used."""
    dev_reg = async_get(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id=integration.entry_id, identifiers={("test", "test")}
    )
    with pytest.raises(ValueError):
        await async_get_device_diagnostics(hass, integration, device)
