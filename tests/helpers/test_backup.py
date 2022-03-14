"""Test backup helpers."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import backup

from tests.components.backup.common import setup_backup_integration


async def test_register_callbacks(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test registering callbacks for the backup manager."""
    assert await setup_backup_integration(hass=hass)

    backup.register_backup_callback(
        hass,
        finish=AsyncMock(),
        start=AsyncMock(),
    )

    assert "Registering backup finish callback for" in caplog.text
    assert "Registering backup start callback for" in caplog.text
