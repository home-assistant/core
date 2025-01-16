"""Tests for the number platform."""

from unittest.mock import patch

import pytest
import requests_mock

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .common import ENTITY_HUMIDIFIER_MIST_LEVEL, build_device_config_entry

from tests.common import MockConfigEntry


async def test_set_mist_level_bad_range(
    hass: HomeAssistant, humidifier_config_entry: MockConfigEntry
) -> None:
    """Test set_mist_level invalid value."""
    with (
        pytest.raises(ServiceValidationError),
        patch(
            "pyvesync.vesyncfan.VeSyncHumid200300S.set_mist_level",
            return_value=True,
        ) as method_mock,
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: ENTITY_HUMIDIFIER_MIST_LEVEL, ATTR_VALUE: "10"},
            blocking=True,
        )
    await hass.async_block_till_done()
    method_mock.assert_not_called()


async def test_set_mist_level(
    hass: HomeAssistant, humidifier_config_entry: MockConfigEntry
) -> None:
    """Test set_mist_level usage."""

    with patch(
        "pyvesync.vesyncfan.VeSyncHumid200300S.set_mist_level",
        return_value=True,
    ) as method_mock:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: ENTITY_HUMIDIFIER_MIST_LEVEL, ATTR_VALUE: "3"},
            blocking=True,
        )
    await hass.async_block_till_done()
    method_mock.assert_called_once()


async def test_mist_level(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker, config
) -> None:
    """Test the state of mist_level number entity."""

    await build_device_config_entry(hass, requests_mock, config, "Humidifier 200s")
    assert hass.states.get(ENTITY_HUMIDIFIER_MIST_LEVEL).state == "6"


async def test_mist_level_availability(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker, config
) -> None:
    """Test the state of mist_level number entity availability."""

    def make_mode_auto(device_name, json) -> None:
        json["result"]["result"]["mode"] = "auto"

    # Mock a humidifier with "auto" mode where mist_level should be unavailable
    await build_device_config_entry(
        hass, requests_mock, config, "Humidifier 200s", make_mode_auto
    )
    assert hass.states.get(ENTITY_HUMIDIFIER_MIST_LEVEL).state == STATE_UNAVAILABLE
