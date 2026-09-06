"""Test Nintendo Parental Controls service calls."""

from typing import Any
from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.nintendo_parental_controls.const import (
    ATTR_BONUS_TIME,
    DOMAIN,
)
from homeassistant.components.nintendo_parental_controls.services import (
    NintendoParentalServices,
)
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID, CONF_PIN
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, Context, HomeAssistant
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration
from .const import PLAYER_ENTITY_ID

from tests.common import MockConfigEntry, MockUser


async def test_add_bonus_time(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_client: AsyncMock,
    mock_nintendo_device: AsyncMock,
) -> None:
    """Test add bonus time service."""
    await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "testdevid"), mock_config_entry.entry_id
    )
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
    ("service", "payload", "return_response", "exception_domain", "exception_key"),
    [
        (
            NintendoParentalServices.ADD_BONUS_TIME,
            {ATTR_DEVICE_ID: "invalid_device", ATTR_BONUS_TIME: 15},
            False,
            HOMEASSISTANT_DOMAIN,
            "service_device_not_found",
        ),
        (
            NintendoParentalServices.UPDATE_PIN_CODE,
            {ATTR_DEVICE_ID: "invalid_device", CONF_PIN: "1234"},
            False,
            HOMEASSISTANT_DOMAIN,
            "service_device_not_found",
        ),
        (
            NintendoParentalServices.UPDATE_PIN_CODE,
            {ATTR_DEVICE_ID: "invalid_device", CONF_PIN: "123"},
            False,
            DOMAIN,
            "invalid_pin_length",
        ),
        (
            NintendoParentalServices.UPDATE_PIN_CODE,
            {ATTR_DEVICE_ID: "invalid_device", CONF_PIN: "123456789"},
            False,
            DOMAIN,
            "invalid_pin_length",
        ),
        (
            NintendoParentalServices.UPDATE_PIN_CODE,
            {ATTR_DEVICE_ID: "invalid_device", CONF_PIN: "0000"},
            False,
            HOMEASSISTANT_DOMAIN,
            "service_device_not_found",
        ),
        (
            NintendoParentalServices.UPDATE_PIN_CODE,
            {ATTR_DEVICE_ID: "invalid_device", CONF_PIN: "abc"},
            False,
            DOMAIN,
            "invalid_pin_length",
        ),
        (
            NintendoParentalServices.DEVICE_USAGE_REPORT,
            {ATTR_DEVICE_ID: "invalid_device"},
            True,
            HOMEASSISTANT_DOMAIN,
            "service_device_not_found",
        ),
        (
            NintendoParentalServices.PLAYER_USAGE_REPORT,
            {ATTR_DEVICE_ID: "invalid_device", ATTR_ENTITY_ID: PLAYER_ENTITY_ID},
            True,
            HOMEASSISTANT_DOMAIN,
            "service_device_not_found",
        ),
    ],
)
async def test_service_no_device_exceptions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_client: AsyncMock,
    service: NintendoParentalServices,
    payload: dict[str, Any],
    return_response: bool,
    exception_domain: str,
    exception_key: str,
) -> None:
    """Test service exceptions."""
    await setup_integration(hass, mock_config_entry)
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, service, payload, blocking=True, return_response=return_response
        )
    assert err.value.translation_domain == exception_domain
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
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "testdevid"), mock_config_entry.entry_id
    )
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


async def test_update_pin_code_requires_admin(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    hass_read_only_user: MockUser,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_client: AsyncMock,
    mock_nintendo_device: AsyncMock,
) -> None:
    """Test updating the PIN code requires administrator access."""
    await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "testdevid"), mock_config_entry.entry_id
    )
    assert device_entry
    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            NintendoParentalServices.UPDATE_PIN_CODE,
            {
                ATTR_DEVICE_ID: device_entry.id,
                CONF_PIN: "1234",
            },
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )
    mock_nintendo_device.set_new_pin.assert_not_called()


async def test_get_player_application_report(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_client: AsyncMock,
    mock_nintendo_device: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device usage report retrieval."""
    await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "testdevid"), mock_config_entry.entry_id
    )
    assert device_entry
    player_entity = entity_registry.async_get(PLAYER_ENTITY_ID)
    assert player_entity
    response = await hass.services.async_call(
        DOMAIN,
        NintendoParentalServices.PLAYER_USAGE_REPORT,
        {ATTR_DEVICE_ID: device_entry.id, ATTR_ENTITY_ID: PLAYER_ENTITY_ID},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


async def test_get_device_application_report(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_client: AsyncMock,
    mock_nintendo_device: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device usage report retrieval."""
    await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "testdevid"), mock_config_entry.entry_id
    )
    assert device_entry
    player_entity = entity_registry.async_get(PLAYER_ENTITY_ID)
    assert player_entity
    response = await hass.services.async_call(
        DOMAIN,
        NintendoParentalServices.DEVICE_USAGE_REPORT,
        {
            ATTR_DEVICE_ID: device_entry.id,
        },
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


@pytest.mark.parametrize(
    ("service", "payload", "return_response", "exception_domain", "exception_key"),
    [
        (
            NintendoParentalServices.PLAYER_USAGE_REPORT,
            {ATTR_ENTITY_ID: "sensor.not_found"},
            True,
            DOMAIN,
            "invalid_entity",
        ),
        (
            NintendoParentalServices.PLAYER_USAGE_REPORT,
            {ATTR_ENTITY_ID: "sensor.home_assistant_test_screen_time_remaining"},
            True,
            DOMAIN,
            "invalid_player",
        ),
    ],
)
async def test_player_service_failures(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_client: AsyncMock,
    service: NintendoParentalServices,
    payload: dict[str, Any],
    return_response: bool,
    exception_domain: str,
    exception_key: str,
) -> None:
    """Test that player specific services raise expected exceptions."""
    await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "testdevid"), mock_config_entry.entry_id
    )
    assert device_entry
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            service,
            {ATTR_DEVICE_ID: device_entry.id, **payload},
            blocking=True,
            return_response=return_response,
        )
    assert err.value.translation_domain == exception_domain
    assert err.value.translation_key == exception_key
