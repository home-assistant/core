"""Test Nintendo Parental Controls service calls."""

from typing import Any
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.nintendo_parental_controls.const import (
    ATTR_BONUS_TIME,
    DOMAIN,
)
from homeassistant.components.nintendo_parental_controls.services import (
    NintendoParentalServices,
)
from homeassistant.const import ATTR_DEVICE_ID, CONF_PIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


async def test_add_bonus_time(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_client: AsyncMock,
    mock_nintendo_device: AsyncMock,
) -> None:
    """Test add bonus time service."""
    await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "testdevid")})
    assert device_entry
    await hass.services.async_call(
        DOMAIN,
        NintendoParentalServices.ADD_BONUS_TIME,
        {
            ATTR_DEVICE_ID: device_entry.id,
            ATTR_BONUS_TIME: 15,
        },
        blocking=True,
    )
    assert len(mock_nintendo_device.add_extra_time.mock_calls) == 1


@pytest.mark.parametrize(
    ("service", "payload", "exception_key"),
    [
        (
            NintendoParentalServices.ADD_BONUS_TIME,
            {ATTR_DEVICE_ID: "invalid_device", ATTR_BONUS_TIME: 15},
            "device_not_found",
        ),
        (
            NintendoParentalServices.UPDATE_PIN_CODE,
            {ATTR_DEVICE_ID: "invalid_device", CONF_PIN: "1234"},
            "device_not_found",
        ),
        (
            NintendoParentalServices.UPDATE_PIN_CODE,
            {ATTR_DEVICE_ID: "invalid_device", CONF_PIN: "123"},
            "invalid_pin_length",
        ),
        (
            NintendoParentalServices.UPDATE_PIN_CODE,
            {ATTR_DEVICE_ID: "invalid_device", CONF_PIN: "123456789"},
            "invalid_pin_length",
        ),
    ],
)
async def test_service_no_device_exceptions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_client: AsyncMock,
    service: NintendoParentalServices,
    payload: dict[str, Any],
    exception_key: str,
) -> None:
    """Test service exceptions."""
    await setup_integration(hass, mock_config_entry)
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            service,
            payload,
            blocking=True,
        )
    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == exception_key


@pytest.mark.parametrize(
    ("service", "payload", "exception_key"),
    [
        (
            NintendoParentalServices.ADD_BONUS_TIME,
            {ATTR_BONUS_TIME: 15},
            "invalid_device",
        ),
        (NintendoParentalServices.UPDATE_PIN_CODE, {CONF_PIN: 1234}, "invalid_device"),
    ],
)
async def test_service_invalid_device_exceptions(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_client: AsyncMock,
    service: NintendoParentalServices,
    payload: dict[str, Any],
    exception_key: str,
) -> None:
    """Test service exceptions with a device that is not a valid Nintendo device."""
    await setup_integration(hass, mock_config_entry)
    # Create a device that does not have a Nintendo identifier
    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "00:11:22:33:44:55")},
    )
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            service,
            {
                **payload,
                ATTR_DEVICE_ID: device_entry.id,
            },
            blocking=True,
        )
    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == exception_key


async def test_update_pin_code(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_client: AsyncMock,
    mock_nintendo_device: AsyncMock,
) -> None:
    """Test update pin code service."""
    await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device(identifiers={(DOMAIN, "testdevid")})
    assert device_entry
    await hass.services.async_call(
        DOMAIN,
        NintendoParentalServices.UPDATE_PIN_CODE,
        {
            ATTR_DEVICE_ID: device_entry.id,
            CONF_PIN: "1234",
        },
        blocking=True,
    )
    assert len(mock_nintendo_device.set_new_pin.mock_calls) == 1
