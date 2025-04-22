"""Test the switchbot entities."""

from collections.abc import Callable
from unittest.mock import patch

import pytest
from switchbot.devices.device import CharacteristicMissingError, SwitchbotOperationError

from homeassistant.components.humidifier import DOMAIN as HUMIDIFIER_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import HUMIDIFIER_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.parametrize(
    ("exception", "error_message"),
    [
        (
            SwitchbotOperationError("Operation failed"),
            "An error occurred while check command result: Operation failed",
        ),
        (
            CharacteristicMissingError("Characteristic missing"),
            "An error occurred while Get a characteristic by handle or UUID: Characteristic missing",
        ),
    ],
)
async def test_exception_handling(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
    exception: type[Exception],
    error_message: str,
) -> None:
    """Test exception handling for switchbot entities."""
    inject_bluetooth_service_info(hass, HUMIDIFIER_SERVICE_INFO)

    entry = mock_entry_factory(sensor_type="humidifier")
    entry.add_to_hass(hass)
    entity_id = "humidifier.test_name"

    with patch(
        "homeassistant.components.switchbot.humidifier.switchbot.SwitchbotHumidifier.turn_on",
    ) as mock_turn_on:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        mock_turn_on.side_effect = exception
        with pytest.raises(HomeAssistantError, match=error_message):
            await hass.services.async_call(
                HUMIDIFIER_DOMAIN,
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: entity_id},
                blocking=True,
            )
