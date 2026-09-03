"""Test Nintendo Parental Controls service calls."""

from datetime import time
from typing import Any
from unittest.mock import AsyncMock

from pynintendoparental.exceptions import (
    BedtimeOutOfRangeError,
    ExtraPlayingTimeActiveError,
    InvalidDeviceStateError,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.nintendo_parental_controls.const import (
    ATTR_BEDTIME_END,
    ATTR_BEDTIME_START,
    ATTR_BONUS_TIME,
    ATTR_DAY_OF_WEEK,
    ATTR_MAX_PLAY_TIME,
    BEDTIME_ALARM_MAX,
    BEDTIME_ALARM_MIN,
    BEDTIME_END_TIME_MAX,
    BEDTIME_END_TIME_MIN,
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
        (
            NintendoParentalServices.UPDATE_DAILY_RESTRICTIONS,
            {ATTR_DEVICE_ID: "invalid_device", ATTR_DAY_OF_WEEK: "monday"},
            False,
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


@pytest.mark.parametrize(
    ("service", "payload", "func"),
    [
        (
            NintendoParentalServices.UPDATE_PIN_CODE,
            {
                CONF_PIN: "1234",
            },
            "set_new_pin",
        ),
        (
            NintendoParentalServices.UPDATE_DAILY_RESTRICTIONS,
            {
                ATTR_DAY_OF_WEEK: "monday",
                ATTR_BEDTIME_START: "20:00",
                ATTR_BEDTIME_END: "22:00",
            },
            "set_daily_restrictions",
        ),
    ],
)
async def test_service_requires_admin(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    hass_read_only_user: MockUser,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_client: AsyncMock,
    mock_nintendo_device: AsyncMock,
    service: NintendoParentalServices,
    payload: dict[str, Any],
    func: str,
) -> None:
    """Test that admin-only services require administrator access."""
    await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "testdevid"), mock_config_entry.entry_id
    )
    assert device_entry
    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            service,
            {**payload, ATTR_DEVICE_ID: device_entry.id},
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )
    getattr(mock_nintendo_device, func).assert_not_called()


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


async def test_update_daily_restrictions(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_client: AsyncMock,
    mock_nintendo_device: AsyncMock,
) -> None:
    """Ensure that the daily restrictions update as expected."""
    await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "testdevid"), mock_config_entry.entry_id
    )
    assert device_entry
    await hass.services.async_call(
        DOMAIN,
        NintendoParentalServices.UPDATE_DAILY_RESTRICTIONS,
        {
            ATTR_DEVICE_ID: device_entry.id,
            ATTR_DAY_OF_WEEK: "monday",
            ATTR_BEDTIME_START: time(21, 0, 0),
            ATTR_BEDTIME_END: time(9, 0, 0),
            ATTR_MAX_PLAY_TIME: 360,
        },
        blocking=True,
    )
    assert len(mock_nintendo_device.set_daily_restrictions.mock_calls) == 1
    mock_nintendo_device.set_daily_restrictions.assert_called_once_with(
        enabled=True,
        bedtime_enabled=True,
        day_of_week="monday",
        bedtime_start=time(9, 0, 0),
        bedtime_end=time(21, 0, 0),
        max_daily_playtime=360,
    )


@pytest.mark.parametrize(
    ("side_effect", "translation_key", "translation_placeholders"),
    [
        pytest.param(
            InvalidDeviceStateError("Invalid device state"),
            "requires_daily_restrictions",
            None,
            id="requires_daily_restrictions",
        ),
        pytest.param(
            ExtraPlayingTimeActiveError("Extra playing time active"),
            "extra_playing_time_active",
            None,
            id="extra_playing_time_active",
        ),
        pytest.param(
            BedtimeOutOfRangeError("Bedtime out of range"),
            "bedtime_out_of_range",
            {
                "bedtime_alarm_min": BEDTIME_ALARM_MIN,
                "bedtime_alarm_max": BEDTIME_ALARM_MAX,
                "bedtime_end_time_min": BEDTIME_END_TIME_MIN,
                "bedtime_end_time_max": BEDTIME_END_TIME_MAX,
            },
            id="bedtime_out_of_range",
        ),
    ],
)
@pytest.mark.usefixtures("mock_nintendo_client")
async def test_update_daily_restrictions_exceptions(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_nintendo_device: AsyncMock,
    side_effect: Exception,
    translation_key: str,
    translation_placeholders: dict[str, str] | None,
) -> None:
    """Test update daily restrictions raises expected exceptions."""
    mock_nintendo_device.set_daily_restrictions.side_effect = side_effect
    await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "testdevid"), mock_config_entry.entry_id
    )
    assert device_entry
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            NintendoParentalServices.UPDATE_DAILY_RESTRICTIONS,
            {
                ATTR_DEVICE_ID: device_entry.id,
                ATTR_DAY_OF_WEEK: "monday",
                ATTR_MAX_PLAY_TIME: 360,
            },
            blocking=True,
        )
    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == translation_key
    assert err.value.translation_placeholders == translation_placeholders
