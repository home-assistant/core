"""Tests for the Backup integration."""
import pytest

from homeassistant.core import HomeAssistant

from .common import setup_backup_integration


async def test_first_setup(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the first setup of the integration."""
    assert await setup_backup_integration(hass=hass)
    assert "Creating backup directory" in caplog.text


async def test_setup_with_hassio(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the setup of the integration with hassio enabled."""
    assert not await setup_backup_integration(hass=hass, with_hassio=True)
    assert (
        "The backup integration is not supported on this installation method, please remove it from your configuration"
        in caplog.text
    )
