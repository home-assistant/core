"""Tests for the services module."""

from pyheos import CommandFailedError, HeosError, const
import pytest

from homeassistant.components.heos.const import (
    ATTR_PASSWORD,
    ATTR_USERNAME,
    DOMAIN,
    SERVICE_SIGN_IN,
    SERVICE_SIGN_OUT,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def setup_component(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the component for testing."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()


async def test_sign_in(hass: HomeAssistant, config_entry, controller) -> None:
    """Test the sign-in service."""
    await setup_component(hass, config_entry)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SIGN_IN,
        {ATTR_USERNAME: "test@test.com", ATTR_PASSWORD: "password"},
        blocking=True,
    )

    controller.sign_in.assert_called_once_with("test@test.com", "password")


async def test_sign_in_not_connected(
    hass: HomeAssistant, config_entry, controller, caplog: pytest.LogCaptureFixture
) -> None:
    """Test sign-in service logs error when not connected."""
    await setup_component(hass, config_entry)
    controller.connection_state = const.STATE_RECONNECTING

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SIGN_IN,
        {ATTR_USERNAME: "test@test.com", ATTR_PASSWORD: "password"},
        blocking=True,
    )

    assert controller.sign_in.call_count == 0
    assert "Unable to sign in because HEOS is not connected" in caplog.text


async def test_sign_in_failed(
    hass: HomeAssistant, config_entry, controller, caplog: pytest.LogCaptureFixture
) -> None:
    """Test sign-in service logs error when not connected."""
    await setup_component(hass, config_entry)
    controller.sign_in.side_effect = CommandFailedError("", "Invalid credentials", 6)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SIGN_IN,
        {ATTR_USERNAME: "test@test.com", ATTR_PASSWORD: "password"},
        blocking=True,
    )

    controller.sign_in.assert_called_once_with("test@test.com", "password")
    assert "Sign in failed: Invalid credentials (6)" in caplog.text


async def test_sign_in_unknown_error(
    hass: HomeAssistant, config_entry, controller, caplog: pytest.LogCaptureFixture
) -> None:
    """Test sign-in service logs error for failure."""
    await setup_component(hass, config_entry)
    controller.sign_in.side_effect = HeosError()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SIGN_IN,
        {ATTR_USERNAME: "test@test.com", ATTR_PASSWORD: "password"},
        blocking=True,
    )

    controller.sign_in.assert_called_once_with("test@test.com", "password")
    assert "Unable to sign in" in caplog.text


async def test_sign_out(hass: HomeAssistant, config_entry, controller) -> None:
    """Test the sign-out service."""
    await setup_component(hass, config_entry)

    await hass.services.async_call(DOMAIN, SERVICE_SIGN_OUT, {}, blocking=True)

    assert controller.sign_out.call_count == 1


async def test_sign_out_not_connected(
    hass: HomeAssistant, config_entry, controller, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the sign-out service."""
    await setup_component(hass, config_entry)
    controller.connection_state = const.STATE_RECONNECTING

    await hass.services.async_call(DOMAIN, SERVICE_SIGN_OUT, {}, blocking=True)

    assert controller.sign_out.call_count == 0
    assert "Unable to sign out because HEOS is not connected" in caplog.text


async def test_sign_out_unknown_error(
    hass: HomeAssistant, config_entry, controller, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the sign-out service."""
    await setup_component(hass, config_entry)
    controller.sign_out.side_effect = HeosError()

    await hass.services.async_call(DOMAIN, SERVICE_SIGN_OUT, {}, blocking=True)

    assert controller.sign_out.call_count == 1
    assert "Unable to sign out" in caplog.text
