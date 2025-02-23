"""Tests for the services module."""

from pyheos import CommandAuthenticationError, HeosError
import pytest

from homeassistant.components.heos.const import (
    ATTR_PASSWORD,
    ATTR_USERNAME,
    DOMAIN,
    SERVICE_SIGN_IN,
    SERVICE_SIGN_OUT,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from . import MockHeos

from tests.common import MockConfigEntry


async def test_sign_in(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test the sign-in service."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SIGN_IN,
        {ATTR_USERNAME: "test@test.com", ATTR_PASSWORD: "password"},
        blocking=True,
    )

    controller.sign_in.assert_called_once_with("test@test.com", "password")


async def test_sign_in_failed(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test sign-in service logs error when not connected."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    controller.sign_in.side_effect = CommandAuthenticationError(
        "", "Invalid credentials", 6
    )

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SIGN_IN,
            {ATTR_USERNAME: "test@test.com", ATTR_PASSWORD: "password"},
            blocking=True,
        )

    controller.sign_in.assert_called_once_with("test@test.com", "password")


async def test_sign_in_unknown_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test sign-in service logs error for failure."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    controller.sign_in.side_effect = HeosError()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SIGN_IN,
            {ATTR_USERNAME: "test@test.com", ATTR_PASSWORD: "password"},
            blocking=True,
        )

    controller.sign_in.assert_called_once_with("test@test.com", "password")


async def test_sign_in_not_loaded_raises(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the sign-in service when entry not loaded raises exception."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    assert await hass.config_entries.async_unload(config_entry.entry_id)

    with pytest.raises(HomeAssistantError, match="The HEOS integration is not loaded"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SIGN_IN,
            {ATTR_USERNAME: "test@test.com", ATTR_PASSWORD: "password"},
            blocking=True,
        )


async def test_sign_out(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test the sign-out service."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    await hass.services.async_call(DOMAIN, SERVICE_SIGN_OUT, {}, blocking=True)

    assert controller.sign_out.call_count == 1


async def test_sign_out_not_loaded_raises(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test the sign-out service when entry not loaded raises exception."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    assert await hass.config_entries.async_unload(config_entry.entry_id)

    with pytest.raises(HomeAssistantError, match="The HEOS integration is not loaded"):
        await hass.services.async_call(DOMAIN, SERVICE_SIGN_OUT, {}, blocking=True)


async def test_sign_out_unknown_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, controller: MockHeos
) -> None:
    """Test the sign-out service."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    controller.sign_out.side_effect = HeosError()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(DOMAIN, SERVICE_SIGN_OUT, {}, blocking=True)

    assert controller.sign_out.call_count == 1
