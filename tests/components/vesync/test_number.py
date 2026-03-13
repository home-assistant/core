"""Tests for the number platform."""

from unittest.mock import patch

import pytest

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .common import ENTITY_HUMIDIFIER_600S_WARM_MIST_LEVEL, ENTITY_HUMIDIFIER_MIST_LEVEL

from tests.common import MockConfigEntry


async def test_set_mist_level_bad_range(
    hass: HomeAssistant, humidifier_config_entry: MockConfigEntry
) -> None:
    """Test set_mist_level invalid value."""
    with (
        pytest.raises(ServiceValidationError),
        patch(
            "pyvesync.devices.vesynchumidifier.VeSyncHumid200300S.set_mist_level",
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
        "pyvesync.devices.vesynchumidifier.VeSyncHumid200300S.set_mist_level",
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
    hass: HomeAssistant, humidifier_config_entry: MockConfigEntry
) -> None:
    """Test the state of mist_level number entity."""

    assert hass.states.get(ENTITY_HUMIDIFIER_MIST_LEVEL).state == "6"


async def test_warm_mist_entity_not_created_for_unsupported(
    hass: HomeAssistant, humidifier_config_entry: MockConfigEntry
) -> None:
    """Test warm mist number entity is not created when device does not support it."""
    assert hass.states.get("number.humidifier_200s_warm_mist_level") is None


async def test_set_warm_mist_level(
    hass: HomeAssistant, humidifier_600s_config_entry: MockConfigEntry
) -> None:
    """Test set_warm_level is called with valid value."""
    with patch(
        "pyvesync.devices.vesynchumidifier.VeSyncHumid200300S.set_warm_level",
        return_value=True,
    ) as method_mock:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: ENTITY_HUMIDIFIER_600S_WARM_MIST_LEVEL,
                ATTR_VALUE: 2,
            },
            blocking=True,
        )
    await hass.async_block_till_done()
    method_mock.assert_called_once_with(2)


async def test_set_warm_mist_level_bad_range(
    hass: HomeAssistant, humidifier_600s_config_entry: MockConfigEntry
) -> None:
    """Test set_warm_level invalid value raises and does not call API."""
    with (
        pytest.raises(ServiceValidationError),
        patch(
            "pyvesync.devices.vesynchumidifier.VeSyncHumid200300S.set_warm_level",
            return_value=True,
        ) as method_mock,
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: ENTITY_HUMIDIFIER_600S_WARM_MIST_LEVEL,
                ATTR_VALUE: 10,
            },
            blocking=True,
        )
    await hass.async_block_till_done()
    method_mock.assert_not_called()
