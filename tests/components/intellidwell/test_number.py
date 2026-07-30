"""Test number platform for IntelliDwell Sprinkler Controller."""

from unittest.mock import patch

from pyintellidwell import IntelliDwellConnectionError
import pytest

from homeassistant.components.intellidwell.const import DOMAIN
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_rain_delay_number(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test rain delay number entity setup and value setting."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1"},
        entry_id="mock_entry_num",
    )
    entry.add_to_hass(hass)

    status_data = {
        "relay_states": [0] * 10,
        "timers": {},
        "queue": {},
    }

    with (
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.get_status",
            return_value=status_data,
            create=True,
        ),
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.get_rain_delay",
            return_value={"days_remaining": 3},
            create=True,
        ),
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.get_schedules",
            return_value=[],
            create=True,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "number.intellidwell_sprinkler_controller_rain_delay"
        assert entity_registry.async_is_registered(entity_id)

        state = hass.states.get(entity_id)
        assert state.state == "3.0"

        with patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.set_rain_delay",
            create=True,
        ) as mock_set_rain_delay:
            await hass.services.async_call(
                NUMBER_DOMAIN,
                SERVICE_SET_VALUE,
                {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 2.0},
                blocking=True,
            )
            mock_set_rain_delay.assert_called_once_with(2)


async def test_rain_delay_number_connection_error(hass: HomeAssistant) -> None:
    """Test connection error when setting rain delay value."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1"},
        entry_id="mock_entry_num_err",
    )
    entry.add_to_hass(hass)

    status_data = {
        "relay_states": [0] * 10,
        "timers": {},
        "queue": {},
    }

    with (
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.get_status",
            return_value=status_data,
            create=True,
        ),
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.get_rain_delay",
            return_value={"days_remaining": 0},
            create=True,
        ),
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.get_schedules",
            return_value=[],
            create=True,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "number.intellidwell_sprinkler_controller_rain_delay"

    with (
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.set_rain_delay",
            side_effect=IntelliDwellConnectionError("timeout"),
            create=True,
        ),
        pytest.raises(HomeAssistantError, match="Error setting rain delay to 4 days"),
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 4.0},
            blocking=True,
        )


async def test_rain_delay_number_invalid_value(hass: HomeAssistant) -> None:
    """Test ValueError raised when setting float value for rain delay."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.1.1.1"},
        entry_id="mock_entry_num_invalid",
    )
    entry.add_to_hass(hass)

    status_data = {
        "relay_states": [0] * 10,
        "timers": {},
        "queue": {},
    }

    with (
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.get_status",
            return_value=status_data,
            create=True,
        ),
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.get_rain_delay",
            return_value={"days_remaining": 0},
            create=True,
        ),
        patch(
            "homeassistant.components.intellidwell.IntelliDwellClient.get_schedules",
            return_value=[],
            create=True,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entity_id = "number.intellidwell_sprinkler_controller_rain_delay"

    with pytest.raises(
        ServiceValidationError, match="Rain delay value must be a whole number of days"
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 4.5},
            blocking=True,
        )
