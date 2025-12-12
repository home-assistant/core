"""Test the Eufy Security coordinator."""

from unittest.mock import MagicMock

from eufy_security import (
    CaptchaRequiredError,
    EufySecurityError,
    InvalidCredentialsError,
)
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_coordinator_update_invalid_credentials(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test coordinator handles InvalidCredentialsError."""
    coordinator = init_integration.runtime_data.coordinator

    # Simulate InvalidCredentialsError during update
    coordinator.api.async_update_device_info.side_effect = InvalidCredentialsError(
        "Invalid credentials"
    )

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_coordinator_update_captcha_required(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test coordinator handles CaptchaRequiredError."""
    coordinator = init_integration.runtime_data.coordinator

    # Simulate CaptchaRequiredError during update
    coordinator.api.async_update_device_info.side_effect = CaptchaRequiredError(
        "CAPTCHA required",
        captcha_id="captcha123",
        captcha_image="data:image/png;base64,ABC",
    )

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_coordinator_update_api_error_logs_once(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test coordinator logs unavailability only once."""
    coordinator = init_integration.runtime_data.coordinator
    coordinator._unavailable_logged = False

    # Simulate EufySecurityError during update
    coordinator.api.async_update_device_info.side_effect = EufySecurityError(
        "API error"
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    assert "Eufy Security API is unavailable" in caplog.text
    assert coordinator._unavailable_logged is True

    # Second error should not log again
    caplog.clear()
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    assert "Eufy Security API is unavailable" not in caplog.text


async def test_coordinator_recovery_logging(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_camera: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test coordinator logs recovery when API comes back online."""
    coordinator = init_integration.runtime_data.coordinator
    coordinator._unavailable_logged = True

    # Simulate successful update after being unavailable
    coordinator.api.async_update_device_info.side_effect = None
    coordinator.api.cameras = {mock_camera.serial: mock_camera}
    coordinator.api.stations = {}

    await coordinator._async_update_data()

    assert "Eufy Security API connection restored" in caplog.text
    assert coordinator._unavailable_logged is False
