"""Test ESPHome entry data."""

from unittest.mock import Mock, patch

from aioesphomeapi import (
    APIClient,
    EntityCategory as ESPHomeEntityCategory,
    SensorInfo,
    SensorState,
)

from homeassistant.components.esphome import DOMAIN
from homeassistant.components.esphome.entry_data import RuntimeEntryData
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery_flow, entity_registry as er
from homeassistant.helpers.service_info.esphome import ESPHomeServiceInfo

from .conftest import MockGenericDeviceEntryType


async def test_migrate_entity_unique_id_downgrade_upgrade(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test unique id migration prefers the original entity on downgrade upgrade."""
    entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "my_sensor",
        suggested_object_id="old_sensor",
        disabled_by=None,
    )
    entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "11:22:33:44:55:AA-sensor-mysensor",
        suggested_object_id="new_sensor",
        disabled_by=None,
    )
    entity_info = [
        SensorInfo(
            object_id="mysensor",
            key=1,
            name="my sensor",
            entity_category=ESPHomeEntityCategory.DIAGNOSTIC,
            icon="mdi:leaf",
        )
    ]
    states = [SensorState(key=1, state=50)]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("sensor.new_sensor")
    assert state is not None
    assert state.state == "50"
    entry = entity_registry.async_get("sensor.new_sensor")
    assert entry is not None
    # Confirm we did not touch the entity that was created
    # on downgrade so when they upgrade again they can delete the
    # entity that was only created on downgrade and they keep
    # the original one.
    assert (
        entity_registry.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, "my_sensor")
        is not None
    )
    # Note that ESPHome includes the EntityInfo type in the unique id
    # as this is not a 1:1 mapping to the entity platform (ie. text_sensor)
    assert entry.unique_id == "11:22:33:44:55:AA-sensor-mysensor"


async def test_discover_zwave() -> None:
    """Test ESPHome discovery of Z-Wave JS."""
    hass = Mock()
    entry_data = RuntimeEntryData(
        "mock-id",
        "mock-title",
        Mock(
            connected_address="mock-client-address",
            port=1234,
            noise_psk=None,
        ),
        None,
    )
    device_info = Mock(
        mac_address="mock-device-info-mac",
        zwave_proxy_feature_flags=1,
    )
    device_info.name = "mock-device-infoname"

    with patch(
        "homeassistant.helpers.discovery_flow.async_create_flow"
    ) as mock_create_flow:
        entry_data.async_on_connect(
            hass,
            device_info,
            None,
        )
        mock_create_flow.assert_called_once_with(
            hass,
            "zwave_js",
            {"source": "esphome"},
            ESPHomeServiceInfo(
                name="mock-device-infoname",
                mac_address="mock-device-info-mac",
                ip_address="mock-client-address",
                port=1234,
                noise_psk=None,
            ),
            discovery_key=discovery_flow.DiscoveryKey(
                domain="esphome",
                key="mock-device-info-mac",
                version=1,
            ),
        )
