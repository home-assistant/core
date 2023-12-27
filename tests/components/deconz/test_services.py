"""deCONZ service tests."""
from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant.components.deconz.const import (
    CONF_BRIDGE_ID,
    CONF_MASTER_GATEWAY,
    DOMAIN as DECONZ_DOMAIN,
)
from homeassistant.components.deconz.deconz_event import CONF_DECONZ_EVENT
from homeassistant.components.deconz.services import (
    SERVICE_CONFIGURE_DEVICE,
    SERVICE_DATA,
    SERVICE_DEVICE_REFRESH,
    SERVICE_ENTITY,
    SERVICE_FIELD,
    SERVICE_REMOVE_ORPHANED_ENTRIES,
    SUPPORTED_SERVICES,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_registry import async_entries_for_config_entry

from .test_gateway import (
    BRIDGEID,
    DECONZ_WEB_REQUEST,
    mock_deconz_put_request,
    mock_deconz_request,
    setup_deconz_integration,
)

from tests.common import async_capture_events
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_service_setup_and_unload(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Verify service setup works."""
    config_entry = await setup_deconz_integration(hass, aioclient_mock)
    for service in SUPPORTED_SERVICES:
        assert hass.services.has_service(DECONZ_DOMAIN, service)

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    for service in SUPPORTED_SERVICES:
        assert not hass.services.has_service(DECONZ_DOMAIN, service)


@patch("homeassistant.core.ServiceRegistry.async_remove")
@patch("homeassistant.core.ServiceRegistry.async_register")
async def test_service_setup_and_unload_not_called_if_multiple_integrations_detected(
    register_service_mock,
    remove_service_mock,
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Make sure that services are only setup and removed once."""
    config_entry = await setup_deconz_integration(hass, aioclient_mock)
    register_service_mock.reset_mock()
    config_entry_2 = await setup_deconz_integration(hass, aioclient_mock, entry_id=2)
    register_service_mock.assert_not_called()

    register_service_mock.assert_not_called()
    assert await hass.config_entries.async_unload(config_entry_2.entry_id)
    remove_service_mock.assert_not_called()
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert remove_service_mock.call_count == 3


async def test_configure_service_with_field(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that service invokes pydeconz with the correct path and data."""
    config_entry = await setup_deconz_integration(hass, aioclient_mock)

    data = {
        SERVICE_FIELD: "/lights/2",
        CONF_BRIDGE_ID: BRIDGEID,
        SERVICE_DATA: {"on": True, "attr1": 10, "attr2": 20},
    }

    mock_deconz_put_request(aioclient_mock, config_entry.data, "/lights/2")

    await hass.services.async_call(
        DECONZ_DOMAIN, SERVICE_CONFIGURE_DEVICE, service_data=data, blocking=True
    )
    assert aioclient_mock.mock_calls[1][2] == {"on": True, "attr1": 10, "attr2": 20}


async def test_configure_service_with_entity(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that service invokes pydeconz with the correct path and data."""
    data = {
        "lights": {
            "1": {
                "name": "Test",
                "state": {"reachable": True},
                "type": "Light",
                "uniqueid": "00:00:00:00:00:00:00:01-00",
            }
        }
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        config_entry = await setup_deconz_integration(hass, aioclient_mock)

    data = {
        SERVICE_ENTITY: "light.test",
        SERVICE_DATA: {"on": True, "attr1": 10, "attr2": 20},
    }

    mock_deconz_put_request(aioclient_mock, config_entry.data, "/lights/1")

    await hass.services.async_call(
        DECONZ_DOMAIN, SERVICE_CONFIGURE_DEVICE, service_data=data, blocking=True
    )
    assert aioclient_mock.mock_calls[1][2] == {"on": True, "attr1": 10, "attr2": 20}


async def test_configure_service_with_entity_and_field(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that service invokes pydeconz with the correct path and data."""
    data = {
        "lights": {
            "1": {
                "name": "Test",
                "state": {"reachable": True},
                "type": "Light",
                "uniqueid": "00:00:00:00:00:00:00:01-00",
            }
        }
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        config_entry = await setup_deconz_integration(hass, aioclient_mock)

    data = {
        SERVICE_ENTITY: "light.test",
        SERVICE_FIELD: "/state",
        SERVICE_DATA: {"on": True, "attr1": 10, "attr2": 20},
    }

    mock_deconz_put_request(aioclient_mock, config_entry.data, "/lights/1/state")

    await hass.services.async_call(
        DECONZ_DOMAIN, SERVICE_CONFIGURE_DEVICE, service_data=data, blocking=True
    )
    assert aioclient_mock.mock_calls[1][2] == {"on": True, "attr1": 10, "attr2": 20}


async def test_configure_service_with_faulty_bridgeid(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that service fails on a bad bridge id."""
    await setup_deconz_integration(hass, aioclient_mock)
    aioclient_mock.clear_requests()

    data = {
        CONF_BRIDGE_ID: "Bad bridge id",
        SERVICE_FIELD: "/lights/1",
        SERVICE_DATA: {"on": True},
    }

    await hass.services.async_call(
        DECONZ_DOMAIN, SERVICE_CONFIGURE_DEVICE, service_data=data
    )
    await hass.async_block_till_done()

    assert len(aioclient_mock.mock_calls) == 0


async def test_configure_service_with_faulty_field(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that service fails on a bad field."""
    await setup_deconz_integration(hass, aioclient_mock)

    data = {SERVICE_FIELD: "light/2", SERVICE_DATA: {}}

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DECONZ_DOMAIN, SERVICE_CONFIGURE_DEVICE, service_data=data
        )
        await hass.async_block_till_done()


async def test_configure_service_with_faulty_entity(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that service on a non existing entity."""
    await setup_deconz_integration(hass, aioclient_mock)
    aioclient_mock.clear_requests()

    data = {
        SERVICE_ENTITY: "light.nonexisting",
        SERVICE_DATA: {},
    }

    await hass.services.async_call(
        DECONZ_DOMAIN, SERVICE_CONFIGURE_DEVICE, service_data=data
    )
    await hass.async_block_till_done()

    assert len(aioclient_mock.mock_calls) == 0


async def test_calling_service_with_no_master_gateway_fails(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that service call fails when no master gateway exist."""
    await setup_deconz_integration(
        hass, aioclient_mock, options={CONF_MASTER_GATEWAY: False}
    )
    aioclient_mock.clear_requests()

    data = {
        SERVICE_FIELD: "/lights/1",
        SERVICE_DATA: {"on": True},
    }

    await hass.services.async_call(
        DECONZ_DOMAIN, SERVICE_CONFIGURE_DEVICE, service_data=data
    )
    await hass.async_block_till_done()

    assert len(aioclient_mock.mock_calls) == 0


async def test_service_refresh_devices(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that service can refresh devices."""
    config_entry = await setup_deconz_integration(hass, aioclient_mock)

    assert len(hass.states.async_all()) == 0

    aioclient_mock.clear_requests()

    data = {
        "config": {},
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
                "uniqueid": "00:00:00:00:00:00:00:01-00",
            }
        },
        "sensors": {
            "1": {
                "name": "Sensor 1 name",
                "type": "ZHALightLevel",
                "state": {"lightlevel": 30000, "dark": False},
                "config": {"reachable": True},
                "uniqueid": "00:00:00:00:00:00:00:02-00",
            }
        },
    }

    mock_deconz_request(aioclient_mock, config_entry.data, data)

    await hass.services.async_call(
        DECONZ_DOMAIN, SERVICE_DEVICE_REFRESH, service_data={CONF_BRIDGE_ID: BRIDGEID}
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 5


async def test_service_refresh_devices_trigger_no_state_update(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Verify that gateway.ignore_state_updates are honored."""
    data = {
        "sensors": {
            "1": {
                "name": "Switch 1",
                "type": "ZHASwitch",
                "state": {"buttonevent": 1000},
                "config": {"battery": 100},
                "uniqueid": "00:00:00:00:00:00:00:01-00",
            }
        }
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        config_entry = await setup_deconz_integration(hass, aioclient_mock)

    assert len(hass.states.async_all()) == 1

    captured_events = async_capture_events(hass, CONF_DECONZ_EVENT)

    aioclient_mock.clear_requests()

    data = {
        "config": {},
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
                "uniqueid": "00:00:00:00:00:00:00:01-00",
            }
        },
        "sensors": {
            "1": {
                "name": "Switch 1",
                "type": "ZHASwitch",
                "state": {"buttonevent": 1000},
                "config": {"battery": 100},
                "uniqueid": "00:00:00:00:00:00:00:01-00",
            }
        },
    }

    mock_deconz_request(aioclient_mock, config_entry.data, data)

    await hass.services.async_call(
        DECONZ_DOMAIN, SERVICE_DEVICE_REFRESH, service_data={CONF_BRIDGE_ID: BRIDGEID}
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 5
    assert len(captured_events) == 0


async def test_remove_orphaned_entries_service(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test service works and also don't remove more than expected."""
    data = {
        "lights": {
            "1": {
                "name": "Light 1 name",
                "state": {"reachable": True},
                "type": "Light",
                "uniqueid": "00:00:00:00:00:00:00:01-00",
            }
        },
        "sensors": {
            "1": {
                "name": "Switch 1",
                "type": "ZHASwitch",
                "state": {"buttonevent": 1000, "gesture": 1},
                "config": {"battery": 100},
                "uniqueid": "00:00:00:00:00:00:00:03-00",
            },
        },
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        config_entry = await setup_deconz_integration(hass, aioclient_mock)

    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "123")},
    )

    assert (
        len(
            [
                entry
                for entry in device_registry.devices.values()
                if config_entry.entry_id in entry.config_entries
            ]
        )
        == 5  # Host, gateway, light, switch and orphan
    )

    entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DECONZ_DOMAIN,
        "12345",
        suggested_object_id="Orphaned sensor",
        config_entry=config_entry,
        device_id=device.id,
    )

    assert (
        len(async_entries_for_config_entry(entity_registry, config_entry.entry_id))
        == 3  # Light, switch battery and orphan
    )

    await hass.services.async_call(
        DECONZ_DOMAIN,
        SERVICE_REMOVE_ORPHANED_ENTRIES,
        service_data={CONF_BRIDGE_ID: BRIDGEID},
    )
    await hass.async_block_till_done()

    assert (
        len(
            [
                entry
                for entry in device_registry.devices.values()
                if config_entry.entry_id in entry.config_entries
            ]
        )
        == 4  # Host, gateway, light and switch
    )

    assert (
        len(async_entries_for_config_entry(entity_registry, config_entry.entry_id))
        == 2  # Light and switch battery
    )
