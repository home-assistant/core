"""Tests for Victron GX MQTT switches."""

from unittest.mock import patch

from paho.mqtt.client import MQTTMessageInfo
from paho.mqtt.enums import MQTTErrorCode
import pytest
from pytest_homeassistant.common import MockConfigEntry
from victron_mqtt import Hub as VictronVenusHub, NotConnectedError, PublishError
from victron_mqtt.testing import finalize_injection, inject_message

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.victron_gx.const import (
    BINARY_SENSOR_OFF_ID,
    BINARY_SENSOR_ON_ID,
    DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import MOCK_INSTALLATION_ID


async def test_victron_switch(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test SWITCH MetricKind - EV charger charge switch is created and updated."""
    victron_hub, mock_config_entry = init_integration

    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/evcharger/0/StartStop",
        '{"value": 1}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    assert len(entities) == 1
    entity = entities[0]
    assert entity.entity_id == "switch.ev_charging_station_ev_charging"
    assert entity.unique_id == f"{MOCK_INSTALLATION_ID}_evcharger_0_evcharger_charge"
    assert entity.translation_key == "evcharger_charge"

    state = hass.states.get(entity.entity_id)
    assert state is not None
    assert state.state == BINARY_SENSOR_ON_ID

    # Verify device info was registered correctly
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{MOCK_INSTALLATION_ID}_evcharger_0"), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.manufacturer == "Victron Energy"

    # Update the metric to exercise the entity update callback path.
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/evcharger/0/StartStop",
        '{"value": 0}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    state = hass.states.get(entity.entity_id)
    assert state is not None
    assert state.state == BINARY_SENSOR_OFF_ID


async def test_victron_switch_actions(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
    entity_registry: er.EntityRegistry,
) -> None:
    """Test switch turn_on and turn_off service calls update the entity state."""
    victron_hub, mock_config_entry = init_integration

    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/evcharger/0/StartStop",
        '{"value": 0}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    entity_id = entities[0].entity_id

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == BINARY_SENSOR_OFF_ID

    # Call turn_on and turn_off services and assert they update entity state
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": entity_id}, blocking=True
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == BINARY_SENSOR_ON_ID

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": entity_id}, blocking=True
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == BINARY_SENSOR_OFF_ID


@pytest.mark.parametrize(
    "topic",
    [
        pytest.param("evcharger/0/StartStop", id="switch"),
        pytest.param("settings/0/Settings/Services/Bol", id="formula-switch"),
    ],
)
@pytest.mark.parametrize(
    ("return_code", "error_type", "translation_key", "message"),
    [
        pytest.param(
            MQTTErrorCode.MQTT_ERR_NO_CONN,
            NotConnectedError,
            "not_connected",
            "Cannot send the command because the GX device is disconnected",
            id="disconnected",
        ),
        pytest.param(
            MQTTErrorCode.MQTT_ERR_QUEUE_SIZE,
            PublishError,
            "publish_failed",
            "Failed to send the command to the GX device",
            id="publish-failed",
        ),
    ],
)
async def test_switch_action_transport_failure(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
    entity_registry: er.EntityRegistry,
    topic: str,
    return_code: MQTTErrorCode,
    error_type: type[Exception],
    translation_key: str,
    message: str,
) -> None:
    """Test transport failures for regular and formula-backed switches."""
    victron_hub, config_entry = init_integration
    await inject_message(
        victron_hub, f"N/{MOCK_INSTALLATION_ID}/{topic}", '{"value": 0}'
    )
    await finalize_injection(victron_hub, disconnect=False)
    await hass.async_block_till_done()
    entity = next(
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entry.domain == SWITCH_DOMAIN
    )
    result = MQTTMessageInfo(1)
    result.rc = return_code

    with (
        patch.object(victron_hub._client, "publish", return_value=result) as publish,
        pytest.raises(HomeAssistantError) as err,
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity.entity_id},
            blocking=True,
        )

    publish.assert_called_once()
    assert type(err.value) is HomeAssistantError
    assert isinstance(err.value.__cause__, error_type)
    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == translation_key
    assert str(err.value) == message
