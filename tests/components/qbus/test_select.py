"""Test Qbus selects."""

from collections.abc import Awaitable, Callable
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_mqtt_message, snapshot_platform
from tests.typing import MqttMockHAClient

_PAYLOAD_STEPPER_STATE_THE_HOTSTEPPER = (
    '{"id":"UL90","properties":{"value":2},"type":"state"}'
)
_PAYLOAD_STEPPER_SET_THE_HOTSTEPPER = (
    '{"id": "UL90", "type": "state", "properties": {"value": 2}}'
)

_TOPIC_STEPPER_STATE = "cloudapp/QBUSMQTTGW/UL1/UL90/state"
_TOPIC_STEPPER_SET_STATE = "cloudapp/QBUSMQTTGW/UL1/UL90/setState"

_STEPPER_ENTITY_ID = "select.ctd_000001_stepper"


async def test_select(
    hass: HomeAssistant,
    setup_integration_deferred: Callable[[], Awaitable],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test select."""

    with patch("homeassistant.components.qbus.PLATFORMS", [Platform.SELECT]):
        await setup_integration_deferred()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_select_option_updates_stepper(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    setup_integration: None,
) -> None:
    """Test selecting an option."""

    state = hass.states.get(_STEPPER_ENTITY_ID)
    assert state is not None

    options = state.attributes["options"]
    assert options

    mqtt_mock.reset_mock()
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: _STEPPER_ENTITY_ID,
            ATTR_OPTION: "the hotstepper",
        },
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        _TOPIC_STEPPER_SET_STATE,
        _PAYLOAD_STEPPER_SET_THE_HOTSTEPPER,
        0,
        False,
        message_expiry_interval=None,
    )

    async_fire_mqtt_message(
        hass, _TOPIC_STEPPER_STATE, _PAYLOAD_STEPPER_STATE_THE_HOTSTEPPER
    )
    await hass.async_block_till_done()

    entity = hass.states.get(_STEPPER_ENTITY_ID)
    assert entity.state == "the hotstepper"


async def test_select_with_unknown_option(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    setup_integration: None,
) -> None:
    """Test select with passing an unknown option value."""

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: _STEPPER_ENTITY_ID,
                ATTR_OPTION: "I'm the lyrical gangster",
            },
            blocking=True,
        )
