"""Tests for ScreenLogic integration init."""
from unittest.mock import patch

import pytest
from screenlogicpy.const.common import (
    SL_GATEWAY_IP,
    SL_GATEWAY_NAME,
    SL_GATEWAY_PORT,
    SL_GATEWAY_SUBTYPE,
    SL_GATEWAY_TYPE,
)

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.screenlogic import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import slugify

from .conftest import (
    MOCK_ADAPTER_IP,
    MOCK_ADAPTER_MAC,
    MOCK_ADAPTER_NAME,
    MOCK_ADAPTER_PORT,
)

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("entity_data", "old_eid", "new_eid", "new_uid", "new_name"),
    [
        (
            {
                "domain": BINARY_SENSOR_DOMAIN,
                "platform": DOMAIN,
                "unique_id": f"{MOCK_ADAPTER_MAC}_chem_alarm",
                "suggested_object_id": f"{MOCK_ADAPTER_NAME} Chemistry Alarm",
                "disabled_by": None,
                "has_entity_name": True,
                "original_name": "Chemistry Alarm",
            },
            f"binary_sensor.{slugify(MOCK_ADAPTER_NAME)}_chemistry_alarm",
            f"binary_sensor.{slugify(MOCK_ADAPTER_NAME)}_active_alert",
            f"{MOCK_ADAPTER_MAC}_active_alert",
            "Active Alert",
        ),
        (
            {
                "domain": SENSOR_DOMAIN,
                "platform": DOMAIN,
                "unique_id": f"{MOCK_ADAPTER_MAC}_currentWatts_0",
                "suggested_object_id": f"{MOCK_ADAPTER_NAME} Pool Pump Current Watts",
                "disabled_by": None,
                "has_entity_name": True,
                "original_name": "Pool Pump Current Watts",
            },
            f"sensor.{slugify(MOCK_ADAPTER_NAME)}_pool_pump_current_watts",
            f"sensor.{slugify(MOCK_ADAPTER_NAME)}_pool_pump_watts_now",
            f"{MOCK_ADAPTER_MAC}_pump_0_watts_now",
            "Pool Pump Watts Now",
        ),
        (
            {
                "domain": BINARY_SENSOR_DOMAIN,
                "platform": DOMAIN,
                "unique_id": f"{MOCK_ADAPTER_MAC}_scg_status",
                "suggested_object_id": f"{MOCK_ADAPTER_NAME} SCG Status",
                "disabled_by": None,
                "has_entity_name": True,
                "original_name": "SCG Status",
            },
            f"binary_sensor.{slugify(MOCK_ADAPTER_NAME)}_scg_status",
            f"binary_sensor.{slugify(MOCK_ADAPTER_NAME)}_chlorinator",
            f"{MOCK_ADAPTER_MAC}_scg_state",
            "Chlorinator",
        ),
    ],
)
async def test_async_migrate_entries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway,
    entity_data: dict,
    old_eid: str,
    new_eid: str,
    new_uid: str,
    new_name: str,
) -> None:
    """Test migration to new entity names."""

    mock_config_entry.add_to_hass(hass)

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    device: dr.DeviceEntry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, MOCK_ADAPTER_MAC)},
    )

    entity: er.RegistryEntry = entity_registry.async_get_or_create(
        **entity_data, device_id=device.id, config_entry=mock_config_entry
    )
    assert entity.unique_id == entity_data["unique_id"]
    assert entity.entity_id == old_eid
    with patch(
        "homeassistant.components.screenlogic.async_get_connect_info",
        return_value={
            SL_GATEWAY_IP: MOCK_ADAPTER_IP,
            SL_GATEWAY_PORT: MOCK_ADAPTER_PORT,
            SL_GATEWAY_TYPE: 12,
            SL_GATEWAY_SUBTYPE: 2,
            SL_GATEWAY_NAME: MOCK_ADAPTER_NAME,
        },
    ), patch(
        "homeassistant.components.screenlogic.ScreenLogicGateway",
        return_value=mock_gateway,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_migrated = entity_registry.async_get(new_eid)
    assert entity_migrated
    assert entity_migrated.entity_id == new_eid
    assert entity_migrated.unique_id == new_uid
    assert entity_migrated.original_name == new_name
