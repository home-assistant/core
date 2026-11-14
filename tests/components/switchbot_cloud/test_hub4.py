"""Test SwitchBot Hub 4 Cloud sensors."""

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import async_load_json_object_fixture
from pytest_homeassistant.typing import ClientSessionGenerator
from switchbot_api import Device
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switchbot_cloud.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_WEBHOOK_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.helpers import entity_registry as er

from . import configure_integration


@pytest.mark.usefixtures("mock_delete_webhook", "mock_setup_webhook")
@pytest.mark.parametrize("motion", [True, False])
async def test_hub4_polling_and_webhook(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_list_devices: AsyncMock,
    mock_get_status: AsyncMock,
    mock_get_webook_configuration: AsyncMock,
    hass_client_no_auth: ClientSessionGenerator,
    motion: bool,
) -> None:
    """Create all Hub 4 entities and update them through cloud webhooks."""
    await async_process_ha_core_config(hass, {"external_url": "https://example.com"})
    mock_get_webook_configuration.return_value = {"urls": []}
    mock_list_devices.return_value = [
        Device(
            deviceId="B0E9FE582974",
            deviceName="Hub 4",
            deviceType="Hub 4",
            enableCloudService=True,
            hubDeviceId="",
        )
    ]
    status = await async_load_json_object_fixture(hass, "hub4_status.json", DOMAIN)
    status["moveDetected"] = motion
    mock_get_status.return_value = status
    entry = await configure_integration(hass)
    assert entry.state is ConfigEntryState.LOADED
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entities) == 4
    for entity in entities:
        assert entity == snapshot(name=entity.unique_id)
        assert hass.states.get(entity.entity_id) == snapshot(
            name=f"{entity.unique_id}-state"
        )

    client = await hass_client_no_auth()
    for detection_state, expected in (
        ("DETECTED", STATE_ON),
        ("NOT_DETECTED", STATE_OFF),
    ):
        response = await client.post(
            f"/api/webhook/{entry.data[CONF_WEBHOOK_ID]}",
            json={
                "eventType": "changeReport",
                "eventVersion": "1",
                "context": {
                    "deviceMac": "B0E9FE582974",
                    "deviceType": "Hub 4",
                    "detectionState": detection_state,
                    "temperature": 30.3,
                    "humidity": 45,
                    "lightLevel": 1,
                    "scale": "CELSIUS",
                    "timeOfSample": 1742807095763,
                },
            },
        )
        assert response.status == 200
        await hass.async_block_till_done()
        assert hass.states.get("binary_sensor.hub_4_motion").state == expected
        assert hass.states.get("sensor.hub_4_temperature").state == "30.3"
        assert hass.states.get("sensor.hub_4_humidity").state == "45"
        assert hass.states.get("sensor.hub_4_light_level").state == "1"
