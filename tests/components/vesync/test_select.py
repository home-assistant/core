"""Tests for the select platform."""

from unittest.mock import patch

import pytest

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.vesync.const import HUMIDIFIER_NIGHT_LIGHT_LEVEL_DIM
from homeassistant.components.vesync.select import (
    HA_TO_VS_HUMIDIFIER_NIGHT_LIGHT_LEVEL_MAP,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .common import ENTITY_HUMIDIFIER_300S_NIGHT_LIGHT_SELECT, mock_devices_response

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.parametrize(
    "install_humidifier_device", ["humidifier_300s"], indirect=True
)
async def test_humidifier_set_nightlight_level(
    hass: HomeAssistant, humidifier_300s, install_humidifier_device
) -> None:
    """Test set of humidifier night light level."""

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: ENTITY_HUMIDIFIER_300S_NIGHT_LIGHT_SELECT,
            ATTR_OPTION: HUMIDIFIER_NIGHT_LIGHT_LEVEL_DIM,
        },
        blocking=True,
    )

    # Assert that setter API was invoked with the expected translated value
    humidifier_300s.set_nightlight_brightness.assert_called_once_with(
        HA_TO_VS_HUMIDIFIER_NIGHT_LIGHT_LEVEL_MAP[HUMIDIFIER_NIGHT_LIGHT_LEVEL_DIM]
    )


@pytest.mark.parametrize(
    "install_humidifier_device", ["humidifier_300s"], indirect=True
)
async def test_humidifier_nightlight_level(
    hass: HomeAssistant, install_humidifier_device
) -> None:
    """Test the state of humidifier night light level select entity."""

    # The mocked device has night_light_brightness=50 which is "dim"
    assert (
        hass.states.get(ENTITY_HUMIDIFIER_300S_NIGHT_LIGHT_SELECT).state
        == HUMIDIFIER_NIGHT_LIGHT_LEVEL_DIM
    )


async def test_purifier_auto_preference(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the purifier auto mode preference select."""
    mock_devices_response(aioclient_mock, "Air Purifier Vital 200S")

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "select.air_purifier_vital_200s_auto_mode_preference"
    assert hass.states.get(entity_id).state == "default"

    with patch(
        "pyvesync.devices.vesyncpurifier.VeSyncAirBaseV2.set_auto_preference",
        return_value=True,
    ) as method_mock:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "quiet"},
            blocking=True,
        )

    method_mock.assert_called_once_with("quiet")


async def test_no_auto_preference_without_support(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a purifier that reports no auto preference gets no select."""
    mock_devices_response(aioclient_mock, "Air Purifier 200s")

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("fan.air_purifier_200s") is not None
    assert hass.states.get("select.air_purifier_200s_auto_mode_preference") is None
