"""deCONZ service tests without host device."""

from collections.abc import Callable
from typing import Any

import pytest
import voluptuous as vol

from homeassistant.components.deconz.const import CONF_BRIDGE_ID, CONF_MASTER_GATEWAY, DOMAIN
from homeassistant.components.deconz.deconz_event import CONF_DECONZ_EVENT
from homeassistant.components.deconz.services import (
    SERVICE_CONFIGURE_DEVICE,
    SERVICE_DATA,
    SERVICE_DEVICE_REFRESH,
    SERVICE_ENTITY,
    SERVICE_FIELD,
    SERVICE_REMOVE_ORPHANED_ENTRIES,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .test_hub import BRIDGE_ID

from tests.common import MockConfigEntry, async_capture_events
from tests.test_util.aiohttp import AiohttpClientMocker


# ----------------------------
# CONFIGURE_DEVICE Service Tests
# ----------------------------
@pytest.mark.usefixtures("config_entry_setup")
async def test_configure_service_with_field(hass: HomeAssistant, mock_put_request: Callable):
    data = {
        SERVICE_FIELD: "/lights/2",
        CONF_BRIDGE_ID: BRIDGE_ID,
        SERVICE_DATA: {"on": True, "attr1": 10, "attr2": 20},
    }
    aioclient_mock = mock_put_request("/lights/2")

    await hass.services.async_call(
        DOMAIN, SERVICE_CONFIGURE_DEVICE, service_data=data, blocking=True
    )
    assert aioclient_mock.mock_calls[1][2] == {"on": True, "attr1": 10, "attr2": 20}


@pytest.mark.usefixtures("config_entry_setup")
async def test_configure_service_with_entity(hass: HomeAssistant, mock_put_request: Callable):
    data = {
        SERVICE_ENTITY: "light.test",
        SERVICE_DATA: {"on": True, "attr1": 10, "attr2": 20},
    }
    aioclient_mock = mock_put_request("/lights/0")

    await hass.services.async_call(
        DOMAIN, SERVICE_CONFIGURE_DEVICE, service_data=data, blocking=True
    )
    assert aioclient_mock.mock_calls[1][2] == {"on": True, "attr1": 10, "attr2": 20}


@pytest.mark.usefixtures("config_entry_setup")
async def test_configure_service_with_entity_and_field(hass: HomeAssistant, mock_put_request: Callable):
    data = {
        SERVICE_ENTITY: "light.test",
        SERVICE_FIELD: "/state",
        SERVICE_DATA: {"on": True, "attr1": 10, "attr2": 20},
    }
    aioclient_mock = mock_put_request("/lights/0/state")

    await hass.services.async_call(
        DOMAIN, SERVICE_CONFIGURE_DEVICE, service_data=data, blocking=True
    )
    assert aioclient_mock.mock_calls[1][2] == {"on": True, "attr1": 10, "attr2": 20}


# ----------------------------
# DEVICE_REFRESH Service Tests
# ----------------------------
@pytest.mark.usefixtures("config_entry_setup")
async def test_service_refresh_devices(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker,
                                       deconz_payload: dict[str, Any], mock_requests: Callable):
    aioclient_mock.clear_requests()

    deconz_payload |= {
        "groups": {
            "1": {
                "id": "Group 1 id",
                "name": "Group 1 name",
                "type": "LightGroup",
                "state": {},
                "action": {},
                "scenes": [{"id": "1", "name": "Scene 1"}],
                "lights": ["1"],
            }
        },
        "lights": {
            "1": {
                "name": "Light 1 name",
                "state": {"reachable": True},
                "type": "Light",
                "uniqueid": "light-01-uniqueid",
            }
        },
        "sensors": {
            "1": {
                "name": "Switch 1",
                "type": "ZHASwitch",
                "state": {"buttonevent": 1000, "dark": False},
                "config": {"reachable": True, "battery": 100},
                "uniqueid": "switch-01-uniqueid",
            }
        },
    }
    mock_requests()

    await hass.services.async_call(
        DOMAIN, SERVICE_DEVICE_REFRESH, service_data={CONF_BRIDGE_ID: BRIDGE_ID}
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) >= 4  # Gateway + Light + Switch + Group/Scenes


# ----------------------------
# REMOVE_ORPHANED_ENTRIES Service Test
# ----------------------------
@pytest.mark.parametrize(
    "light_payload",
    [
        {
            "name": "Light 0 name",
            "state": {"reachable": True},
            "type": "Light",
            "uniqueid": "light-01-uniqueid",
        }
    ],
)
@pytest.mark.parametrize(
    "sensor_payload",
    [
        {
            "name": "Switch 1",
            "type": "ZHASwitch",
            "state": {"buttonevent": 1000, "gesture": 1},
            "config": {"battery": 100},
            "uniqueid": "switch-01-uniqueid",
        }
    ],
)
async def test_remove_orphaned_entries_service(hass: HomeAssistant,
                                               device_registry: dr.DeviceRegistry,
                                               entity_registry: er.EntityRegistry,
                                               config_entry_setup: MockConfigEntry):
    """Test service removes only orphaned entries, no host device."""

    # Gateway device
    gateway_device = device_registry.async_get_or_create(
        config_entry_id=config_entry_setup.entry_id,
        identifiers={(DOMAIN, BRIDGE_ID)},
        manufacturer="dresden elektronik",
        model="Mock Model",
        name="Mock Gateway",
    )

    # Light device
    light_device = device_registry.async_get_or_create(
        config_entry_id=config_entry_setup.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "light-mac")},
    )

    # Switch device
    switch_device = device_registry.async_get_or_create(
        config_entry_id=config_entry_setup.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "switch-mac")},
    )

    # Orphan device
    orphan_device = device_registry.async_get_or_create(
        config_entry_id=config_entry_setup.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "orphan-mac")},
    )

    assert len([entry for entry in device_registry.devices.values()
                if config_entry_setup.entry_id in entry.config_entries]) == 4

    # Orphan entity
    entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "orphan-entity-id",
        suggested_object_id="Orphaned sensor",
        config_entry=config_entry_setup,
        device_id=orphan_device.id,
    )

    assert len(er.async_entries_for_config_entry(entity_registry, config_entry_setup.entry_id)) == 2

    await hass.services.async_call(
        DOMAIN,
        SERVICE_REMOVE_ORPHANED_ENTRIES,
        service_data={CONF_BRIDGE_ID: BRIDGE_ID},
    )
    await hass.async_block_till_done()

    # Check devices: Orphan removed
    assert len([entry for entry in device_registry.devices.values()
                if config_entry_setup.entry_id in entry.config_entries]) == 3  # Gateway, Light, Switch

    # Check entities: Orphan entity removed
    assert len(er.async_entries_for_config_entry(entity_registry, config_entry_setup.entry_id)) == 1  # Light
