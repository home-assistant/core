"""Test Qbus switch entities."""

from unittest.mock import MagicMock, patch

import pytest
from qbusmqttapi.const import KEY_OUTPUT_PROPERTIES, KEY_PROPERTIES_VALUE
from qbusmqttapi.discovery import QbusMqttOutput
from qbusmqttapi.state import QbusMqttOnOffState

from homeassistant.components.qbus.switch import QbusSwitch
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from .common import qbus_config_entry

from tests.typing import MqttMockHAClient


@pytest.mark.parametrize(
    ("old_value", "new_value"),
    [
        (STATE_OFF, STATE_ON),
        (STATE_ON, STATE_OFF),
    ],
)
async def test_switch_state_received(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    qbus_switch_1: QbusSwitch,
    old_value: str,
    new_value: str,
) -> None:
    """Test receiving state."""
    entry = qbus_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set(qbus_switch_1.entity_id, old_value)

    # Assert old state
    entity = hass.states.get(qbus_switch_1.entity_id)
    assert entity
    assert entity.state == old_value

    # Test receive new state
    with (
        patch.object(
            qbus_switch_1._message_factory,
            "parse_output_state",
            return_value=QbusMqttOnOffState(
                {KEY_OUTPUT_PROPERTIES: {KEY_PROPERTIES_VALUE: new_value == STATE_ON}}
            ),
        ) as mock_output,
    ):
        await qbus_switch_1._state_received(MagicMock())

    assert mock_output

    # Assert new state
    entity = hass.states.get(qbus_switch_1.entity_id)
    assert entity
    assert entity.state == new_value


async def test_switch_turn_on_off(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    qbus_switch_1: QbusSwitch,
) -> None:
    """Test turn on and off."""
    entry = qbus_config_entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set(qbus_switch_1.entity_id, STATE_OFF)

    mqtt_mock.async_publish.reset_mock()
    await qbus_switch_1.async_turn_on()
    assert qbus_switch_1.state == STATE_ON
    assert len(mqtt_mock.async_publish.mock_calls) == 1

    mqtt_mock.async_publish.reset_mock()
    await qbus_switch_1.async_turn_off()
    assert qbus_switch_1.state == STATE_OFF
    assert len(mqtt_mock.async_publish.mock_calls) == 1


async def test_switch_create(hass: HomeAssistant) -> None:
    """Test create method."""
    mock_output = MagicMock(spec=QbusMqttOutput)
    mock_output.ref_id = "000001/10"

    entity = QbusSwitch(mock_output)

    assert isinstance(entity, QbusSwitch)
