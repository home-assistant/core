# File: tests/test_microbees_integration.py

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.microbees.const import BEES, CONNECTOR, DOMAIN
from homeassistant.components.microbees.switch import MBSwitch, async_setup_entry
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


class MockMicroBees:
    async def sendCommand(self, actuator_id, value):
        """Mock method sendCommand"""
        return True  # Mock implementation

    async def getActuatorById(self, actuator_id):
        """Mock method getActuatorById"""
        return MockActuator(id=actuator_id, value=1)  # Mock implementation


class MockActuator:
    """MockActuator"""

    def __init__(self, id, value):
        self.id = id
        self.value = value


class MockBee:
    """MockBee"""

    def __init__(self, active=True, product_id=46, actuators=[]):
        """INIT"""
        self.active = active
        self.productID = product_id
        self.actuators = actuators


class TestMicroBeesIntegration:
    """TestMicroBeesIntegration"""

    def setup_method(self):
        """setup_method"""
        self.hass = HomeAssistant()
        self.config_entry = ConfigEntry(
            version=1,
            domain=DOMAIN,
            title="Test Entry",
            data={},
            source="test",
            connection_class="cloud_poll",
            system_options={},
        )
        self.hass.data[DOMAIN] = {CONNECTOR: MockMicroBees(), BEES: [MockBee()]}

    async def test_async_setup_entry(self):
        """test_async_setup_entry"""
        async_add_entities_mock = MagicMock()

        await async_setup_entry(self.hass, self.config_entry, async_add_entities_mock)

        assert async_add_entities_mock.called
        assert async_add_entities_mock.call_args[0][
            0
        ]  # Check that entities were passed

    def test_mbswitch_entity(self):
        """test_mbswitch_entity"""
        bee = MockBee(actuators=[MockActuator(id="test_actuator", value=0)])
        mbswitch = MBSwitch(bee.actuators[0], self.hass.data[DOMAIN][CONNECTOR])

        assert isinstance(mbswitch, SwitchEntity)
        assert mbswitch.name == "test_actuator"
        assert mbswitch.unique_id == "test_actuator"
        assert mbswitch.is_on is False

        # Mock microBees methods
        with patch.object(mbswitch.microbees, "sendCommand", return_value=True):
            with patch.object(
                mbswitch.microbees,
                "getActuatorById",
                return_value=MockActuator(id="test_actuator", value=1),
            ):
                # Test turn_on
                mbswitch.turn_on()
                assert mbswitch.is_on is True

                # Test turn_off
                mbswitch.turn_off()
                assert mbswitch.is_on is False

                # Test async_update
                mbswitch.async_update()
                assert mbswitch.is_on is True


if __name__ == "__main__":
    pytest.main()
