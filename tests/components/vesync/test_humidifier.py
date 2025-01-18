"""Tests for the humidifier platform."""

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

from .common import (
    ENTITY_HUMIDIFIER,
    ENTITY_HUMIDIFIER_HUMIDITY,
    ENTITY_HUMIDIFIER_MIST_LEVEL,
)

from tests.common import MockConfigEntry

NoException = nullcontext()


async def test_humidifier_state(
    hass: HomeAssistant, humidifier_config_entry: MockConfigEntry
) -> None:
    """Test the resulting setup state is as expected for the platform."""

    expected_entities = [
        ENTITY_HUMIDIFIER,
        ENTITY_HUMIDIFIER_HUMIDITY,
        ENTITY_HUMIDIFIER_MIST_LEVEL,
    ]

    assert humidifier_config_entry.state is ConfigEntryState.LOADED

    for entity_id in expected_entities:
        assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

    state = hass.states.get(ENTITY_HUMIDIFIER)

    # ATTR_HUMIDITY represents the target_humidity which comes from configuration.auto_target_humidity node
    assert state.attributes.get(ATTR_HUMIDITY) == 40


async def test_set_target_humidity_invalid(
    hass: HomeAssistant,
    humidifier_config_entry: MockConfigEntry,
) -> None:
    """Test handling of invalid value in set_humidify method."""

    # Setting value out of range results in ServiceValidationError and
    # VeSyncHumid200300S.set_humidity does not get called.
    with (
        patch("pyvesync.vesyncfan.VeSyncHumid200300S.set_humidity") as method_mock,
        pytest.raises(ServiceValidationError),
    ):
        await hass.services.async_call(
            HUMIDIFIER_DOMAIN,
            SERVICE_SET_HUMIDITY,
            {ATTR_ENTITY_ID: ENTITY_HUMIDIFIER, ATTR_HUMIDITY: 20},
            blocking=True,
        )
    await hass.async_block_till_done()
    method_mock.assert_not_called()


@pytest.mark.parametrize(
    ("api_response", "expectation"),
    [(True, NoException), (False, pytest.raises(HomeAssistantError))],
)
async def test_set_target_humidity(
    hass: HomeAssistant,
    humidifier_config_entry: MockConfigEntry,
    api_response: bool,
    expectation,
) -> None:
    """Test handling of return value from VeSyncHumid200300S.set_humidity."""

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
            {ATTR_ENTITY_ID: ENTITY_HUMIDIFIER, ATTR_HUMIDITY: 54},
            blocking=True,
        )
        await hass.async_block_till_done()
        method_mock.assert_called_once()


@pytest.mark.parametrize(
    ("api_response", "expectation"),
    [(False, pytest.raises(HomeAssistantError)), (True, NoException)],
)
async def test_turn_on(
    hass: HomeAssistant,
    humidifier_config_entry: MockConfigEntry,
    api_response: bool,
    expectation,
) -> None:
    """Test turn_on method."""

    # turn_on returns False indicating failure in which case humidifier.turn_on
    # raises HomeAssistantError.
    with (
        expectation,
        patch(
            "pyvesync.vesyncfan.VeSyncHumid200300S.turn_on", return_value=api_response
        ) as method_mock,
    ):
        with patch(
            "homeassistant.components.vesync.humidifier.VeSyncHumidifierHA.schedule_update_ha_state"
        ) as update_mock:
            await hass.services.async_call(
                HUMIDIFIER_DOMAIN,
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: ENTITY_HUMIDIFIER},
                blocking=True,
            )

        await hass.async_block_till_done()
        method_mock.assert_called_once()
        update_mock.assert_called_once()


@pytest.mark.parametrize(
    ("api_response", "expectation"),
    [(False, pytest.raises(HomeAssistantError)), (True, NoException)],
)
async def test_turn_off(
    hass: HomeAssistant,
    humidifier_config_entry: MockConfigEntry,
    api_response: bool,
    expectation,
) -> None:
    """Test turn_off method."""

    # turn_off returns False indicating failure in which case humidifier.turn_off
    # raises HomeAssistantError.
    with (
        expectation,
        patch(
            "pyvesync.vesyncfan.VeSyncHumid200300S.turn_off", return_value=api_response
        ) as method_mock,
    ):
        with patch(
            "homeassistant.components.vesync.humidifier.VeSyncHumidifierHA.schedule_update_ha_state"
        ) as update_mock:
            await hass.services.async_call(
                HUMIDIFIER_DOMAIN,
                SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: ENTITY_HUMIDIFIER},
                blocking=True,
            )

        await hass.async_block_till_done()
        method_mock.assert_called_once()
        update_mock.assert_called_once()


async def test_set_mode_invalid(
    hass: HomeAssistant,
    humidifier_config_entry: MockConfigEntry,
) -> None:
    """Test handling of invalid value in set_mode method."""

    with patch(
        "pyvesync.vesyncfan.VeSyncHumid200300S.set_humidity_mode"
    ) as method_mock:
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                HUMIDIFIER_DOMAIN,
                SERVICE_SET_MODE,
                {ATTR_ENTITY_ID: ENTITY_HUMIDIFIER, ATTR_MODE: "something_invalid"},
                blocking=True,
            )
        await hass.async_block_till_done()
        method_mock.assert_not_called()


@pytest.mark.parametrize(
    ("api_response", "expectation"),
    [(True, NoException), (False, pytest.raises(HomeAssistantError))],
)
async def test_set_mode(
    hass: HomeAssistant,
    humidifier_config_entry: MockConfigEntry,
    api_response: bool,
    expectation,
) -> None:
    """Test handling of value in set_mode method."""

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
            {ATTR_ENTITY_ID: ENTITY_HUMIDIFIER, ATTR_MODE: "auto"},
            blocking=True,
        )
    await hass.async_block_till_done()
    method_mock.assert_called_once()
