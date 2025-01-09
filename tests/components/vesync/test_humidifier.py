"""Tests for the humidifer module."""

from contextlib import nullcontext
from unittest.mock import patch

import pytest

from homeassistant.components.humidifier import (
    ATTR_HUMIDITY,
    ATTR_MODE,
    DOMAIN as HUMIDIFIER_DOMAIN,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_MODE,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from tests.common import MockConfigEntry

NoException = nullcontext()


async def test_humidifier_state(
    hass: HomeAssistant, humidifier_config_entry: MockConfigEntry
) -> None:
    """Test the resulting setup state is as expected for the platform."""

    humidifier_id = "humidifier.humidifier_200s"
    expected_entities = [
        humidifier_id,
        "sensor.humidifier_200s_humidity",
    ]

    assert humidifier_config_entry.state is ConfigEntryState.LOADED

    for entity_id in expected_entities:
        assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

    assert hass.states.get("sensor.humidifier_200s_humidity").state == "35"

    state = hass.states.get(humidifier_id)

    # ATTR_HUMIDITY represents the target_humidity which comes from configuration.auto_target_humidity node
    assert state.attributes.get(ATTR_HUMIDITY) == 40


async def test_set_target_humidity_invalid(
    hass: HomeAssistant,
    humidifier_config_entry: MockConfigEntry,
) -> None:
    """Test handling of invalid value in set_humidify method."""

    humidifier_entity_id = "humidifier.humidifier_200s"

    # Setting value out of range results in ServiceValidationError and
    # VeSyncHumid200300S.set_humidity does not get called.
    with (
        patch("pyvesync.vesyncfan.VeSyncHumid200300S.set_humidity") as method_mock,
        pytest.raises(ServiceValidationError),
    ):
        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            SERVICE_SET_HUMIDITY,
            {ATTR_ENTITY_ID: humidifier_entity_id, ATTR_HUMIDITY: 20},
            blocking=True,
        )
    await hass.async_block_till_done()
    method_mock.assert_not_called()


@pytest.mark.parametrize(
    ("api_response", "expectation"),
    [(True, NoException), (False, pytest.raises(HomeAssistantError))],
)
async def test_set_target_humidity_VeSync(
    hass: HomeAssistant,
    humidifier_config_entry: MockConfigEntry,
    api_response: bool,
    expectation,
) -> None:
    """Test handling of return value from VeSyncHumid200300S.set_humidity."""

    humidifier_entity_id = "humidifier.humidifier_200s"

    # If VeSyncHumid200300S.set_humidity fails (returns False), then HomeAssistantError is raised
    with (
        expectation,
        patch(
            "pyvesync.vesyncfan.VeSyncHumid200300S.set_humidity",
            return_value=api_response,
        ) as method_mock,
    ):
        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            SERVICE_SET_HUMIDITY,
            {ATTR_ENTITY_ID: humidifier_entity_id, ATTR_HUMIDITY: 54},
            blocking=True,
        )
        await hass.async_block_till_done()
        method_mock.assert_called_once()


@pytest.mark.parametrize(
    ("turn_on", "api_response", "expectation"),
    [
        (False, False, pytest.raises(HomeAssistantError)),
        (False, True, NoException),
        (True, False, pytest.raises(HomeAssistantError)),
        (True, True, NoException),
    ],
)
async def test_turn_on_off(
    hass: HomeAssistant,
    humidifier_config_entry: MockConfigEntry,
    turn_on: bool,
    api_response: bool,
    expectation,
) -> None:
    """Test turn_on/off methods."""

    humidifier_entity_id = "humidifier.humidifier_200s"

    # turn_on/turn_off returns False indicating failure in which case humidifier.turn_on/turn_off
    # raises HomeAssistantError.
    with (
        expectation,
        patch(
            f"pyvesync.vesyncfan.VeSyncHumid200300S.{"turn_on" if turn_on else "turn_off"}",
            return_value=api_response,
        ) as method_mock,
    ):
        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            SERVICE_TURN_ON if turn_on else SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: humidifier_entity_id},
            blocking=True,
        )

        await hass.async_block_till_done()
        method_mock.assert_called_once()


async def test_set_mode_invalid(
    hass: HomeAssistant,
    humidifier_config_entry: MockConfigEntry,
) -> None:
    """Test handling of invalid value in set_mode method."""

    humidifier_entity_id = "humidifier.humidifier_200s"

    with patch(
        "pyvesync.vesyncfan.VeSyncHumid200300S.set_humidity_mode"
    ) as method_mock:
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                HUMIDIFIER_DOMAIN,
                SERVICE_SET_MODE,
                {ATTR_ENTITY_ID: humidifier_entity_id, ATTR_MODE: "something_invalid"},
                blocking=True,
            )
        await hass.async_block_till_done()
        method_mock.assert_not_called()


@pytest.mark.parametrize(
    ("api_response", "expectation"),
    [(True, NoException), (False, pytest.raises(HomeAssistantError))],
)
async def test_set_mode_VeSync(
    hass: HomeAssistant,
    humidifier_config_entry: MockConfigEntry,
    api_response: bool,
    expectation,
) -> None:
    """Test handling of value in set_mode method."""

    humidifier_entity_id = "humidifier.humidifier_200s"

    # If VeSyncHumid200300S.set_humidity_mode fails (returns False), then HomeAssistantError is raised
    with (
        expectation,
        patch(
            "pyvesync.vesyncfan.VeSyncHumid200300S.set_humidity_mode",
            return_value=api_response,
        ) as method_mock,
    ):
        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            SERVICE_SET_MODE,
            {ATTR_ENTITY_ID: humidifier_entity_id, ATTR_MODE: "auto"},
            blocking=True,
        )
    await hass.async_block_till_done()
    method_mock.assert_called_once()
