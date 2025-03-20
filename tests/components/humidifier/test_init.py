"""The tests for the humidifier component."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.humidifier import (
    ATTR_HUMIDITY,
    DOMAIN as HUMIDIFIER_DOMAIN,
    MODE_ECO,
    MODE_NORMAL,
    SERVICE_SET_HUMIDITY,
    HumidifierEntity,
    HumidifierEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from tests.common import MockConfigEntry, MockEntity, setup_test_component_platform


class MockHumidifierEntity(MockEntity, HumidifierEntity):
    """Mock Humidifier device to use in tests."""

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return 0


async def test_sync_turn_on(hass: HomeAssistant) -> None:
    """Test if async turn_on calls sync turn_on."""
    humidifier = MockHumidifierEntity()
    humidifier.hass = hass

    humidifier.turn_on = MagicMock()
    await humidifier.async_turn_on()

    assert humidifier.turn_on.called


async def test_sync_turn_off(hass: HomeAssistant) -> None:
    """Test if async turn_off calls sync turn_off."""
    humidifier = MockHumidifierEntity()
    humidifier.hass = hass

    humidifier.turn_off = MagicMock()
    await humidifier.async_turn_off()

    assert humidifier.turn_off.called


async def test_humidity_validation(
    hass: HomeAssistant,
    register_test_integration: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test validation for humidity."""

    class MockHumidifierEntityHumidity(MockEntity, HumidifierEntity):
        """Mock climate class with mocked aux heater."""

        _attr_supported_features = HumidifierEntityFeature.MODES
        _attr_available_modes = [MODE_NORMAL, MODE_ECO]
        _attr_mode = MODE_NORMAL
        _attr_target_humidity = 50
        _attr_min_humidity = 50
        _attr_max_humidity = 60

        def set_humidity(self, humidity: int) -> None:
            """Set new target humidity."""
            self._attr_target_humidity = humidity

    test_humidifier = MockHumidifierEntityHumidity(
        name="Test",
        unique_id="unique_humidifier_test",
    )

    setup_test_component_platform(
        hass, HUMIDIFIER_DOMAIN, entities=[test_humidifier], from_config_entry=True
    )
    await hass.config_entries.async_setup(register_test_integration.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("humidifier.test")
    assert state.attributes.get(ATTR_HUMIDITY) == 50

    with pytest.raises(
        ServiceValidationError,
        match="Provided humidity 1 is not valid. Accepted range is 50 to 60",
    ) as exc:
        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            SERVICE_SET_HUMIDITY,
            {
                "entity_id": "humidifier.test",
                ATTR_HUMIDITY: "1",
            },
            blocking=True,
        )

    assert exc.value.translation_key == "humidity_out_of_range"
    assert "Check valid humidity 1 in range 50 - 60" in caplog.text

    with pytest.raises(
        ServiceValidationError,
        match="Provided humidity 70 is not valid. Accepted range is 50 to 60",
    ) as exc:
        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            SERVICE_SET_HUMIDITY,
            {
                "entity_id": "humidifier.test",
                ATTR_HUMIDITY: "70",
            },
            blocking=True,
        )
