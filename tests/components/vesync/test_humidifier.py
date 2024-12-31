"""Tests for the humidifer module."""

from contextlib import nullcontext
from unittest.mock import patch

import pytest

from homeassistant.components.humidifier import (
    ATTR_CURRENT_HUMIDITY,
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
from homeassistant.exceptions import ServiceValidationError

from tests.common import MockConfigEntry


async def test_humidifier_state(
    hass: HomeAssistant, humidifier_config_entry: MockConfigEntry
) -> None:
    """Test the resulting setup state is as expected for the platform."""

    humidifier_id = "humidifier.humidifier_200s_none"
    expected_entities = [
        humidifier_id,
        "switch.humidifier_200s_auto_mode",
        "switch.humidifier_200s_automatic_stop",
        "switch.humidifier_200s_display",
        "sensor.humidifier_200s_humidity",
    ]

    assert humidifier_config_entry.state is ConfigEntryState.LOADED

    for entity_id in expected_entities:
        assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

    assert hass.states.get("sensor.humidifier_200s_humidity").state == "35"
    assert hass.states.get("switch.humidifier_200s_auto_mode").state == "off"
    assert hass.states.get("switch.humidifier_200s_automatic_stop").state == "on"
    assert hass.states.get("switch.humidifier_200s_display").state == "on"

    state = hass.states.get(humidifier_id)
    assert state.attributes.get(ATTR_CURRENT_HUMIDITY) == 35


@patch(
    "homeassistant.components.vesync.humidifier.VeSyncHumidifierHA.schedule_update_ha_state"
)
async def test_set_target_humidity_invalid(
    mock_schedule_update_ha_state,
    hass: HomeAssistant,
    humidifier_config_entry: MockConfigEntry,
) -> None:
    """Test handling of invalid value in set_humidify method."""

    humidifier_entity_id = "humidifier.humidifier_200s_none"

    # Setting value out of range results in ServiceValidationError and
    # VeSyncHumid200300S.set_humidity does not get called.
    # humidifier.async_service_humidity_set throws ServiceValidationError if the value
    # is outside MIN_HUMIDITY..MAX_HUMIDITY.
    with patch("pyvesync.vesyncfan.VeSyncHumid200300S.set_humidity") as method_mock:
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                HUMIDIFIER_DOMAIN,
                SERVICE_SET_HUMIDITY,
                {ATTR_ENTITY_ID: humidifier_entity_id, ATTR_HUMIDITY: 20},
                blocking=True,
            )
        await hass.async_block_till_done()
        method_mock.assert_not_called()
        mock_schedule_update_ha_state.assert_not_called()


@patch(
    "homeassistant.components.vesync.humidifier.VeSyncHumidifierHA.schedule_update_ha_state"
)
@pytest.mark.parametrize(
    "success",
    [False, True],
)
async def test_set_target_humidity_VeSync(
    mock_schedule_update_ha_state,
    hass: HomeAssistant,
    humidifier_config_entry: MockConfigEntry,
    success: bool,
) -> None:
    """Test handling of return value from VeSyncHumid200300S.set_humidity."""

    humidifier_entity_id = "humidifier.humidifier_200s_none"

    # If VeSyncHumid200300S.set_humidity fails (returns False), then ValueError is raised
    # and schedule_update_ha_state is not called.
    expectation = nullcontext() if success else pytest.raises(ValueError)
    with (
        expectation,
        patch(
            "pyvesync.vesyncfan.VeSyncHumid200300S.set_humidity", return_value=success
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

        if success:
            mock_schedule_update_ha_state.assert_called_once()
        else:
            mock_schedule_update_ha_state.assert_not_called()


@pytest.mark.parametrize(
    ("turn_on", "success"),
    [(False, False), (False, True), (True, False), (True, True)],
)
async def test_turn_on_off(
    hass: HomeAssistant,
    humidifier_config_entry: MockConfigEntry,
    turn_on: bool,
    success: bool,
) -> None:
    """Test turn_on/off methods."""

    humidifier_entity_id = "humidifier.humidifier_200s_none"

    # turn_on/turn_off returns False indicating failure in which case humidifier.turn_on/turn_off
    # raises ValueError. HA state update is scheduled for success.
    expectation = nullcontext() if success else pytest.raises(ValueError)
    with (
        expectation,
        patch(
            f"pyvesync.vesyncfan.VeSyncHumid200300S.{"turn_on" if turn_on else "turn_off"}",
            return_value=success,
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


@patch(
    "homeassistant.components.vesync.humidifier.VeSyncHumidifierHA.schedule_update_ha_state"
)
async def test_set_mode_invalid(
    mock_schedule_update_ha_state,
    hass: HomeAssistant,
    humidifier_config_entry: MockConfigEntry,
) -> None:
    """Test handling of invalid value in set_mode method."""

    humidifier_entity_id = "humidifier.humidifier_200s_none"

    # Setting invalid value results in ServiceValidationError and
    # VeSyncHumid200300S.set_humidity_mode does not get called.
    with patch(
        "pyvesync.vesyncfan.VeSyncHumid200300S.set_humidity_mode"
    ) as method_mock:
        with pytest.raises(ValueError):
            await hass.services.async_call(
                HUMIDIFIER_DOMAIN,
                SERVICE_SET_MODE,
                {ATTR_ENTITY_ID: humidifier_entity_id, ATTR_MODE: "something_invalid"},
                blocking=True,
            )
        await hass.async_block_till_done()
        method_mock.assert_not_called()
        mock_schedule_update_ha_state.assert_not_called()


@patch(
    "homeassistant.components.vesync.humidifier.VeSyncHumidifierHA.schedule_update_ha_state"
)
@pytest.mark.parametrize(
    "success",
    [False, True],
)
async def test_set_mode_VeSync(
    mock_schedule_update_ha_state,
    hass: HomeAssistant,
    humidifier_config_entry: MockConfigEntry,
    success: bool,
) -> None:
    """Test handling of value in set_mode method."""

    humidifier_entity_id = "humidifier.humidifier_200s_none"

    # If VeSyncHumid200300S.set_humidity_mode itself fails, then we should get ValueError
    expectation = nullcontext() if success else pytest.raises(ValueError)
    with patch(
        "pyvesync.vesyncfan.VeSyncHumid200300S.set_humidity_mode", return_value=success
    ) as method_mock:
        with expectation:
            await hass.services.async_call(
                HUMIDIFIER_DOMAIN,
                SERVICE_SET_MODE,
                {ATTR_ENTITY_ID: humidifier_entity_id, ATTR_MODE: "auto"},
                blocking=True,
            )
        await hass.async_block_till_done()
        method_mock.assert_called_once()

        if success:
            mock_schedule_update_ha_state.assert_called_once()
        else:
            mock_schedule_update_ha_state.assert_not_called()
