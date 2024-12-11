"""Tests for the Backup integration."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.backup.const import DATA_MANAGER, DOMAIN
from homeassistant.core import HomeAssistant

from .common import setup_backup_integration


@pytest.mark.usefixtures("supervisor_client")
async def test_setup_with_hassio(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the setup of the integration with hassio enabled."""
    assert await setup_backup_integration(
        hass=hass,
        with_hassio=True,
        configuration={DOMAIN: {}},
    )
    manager = hass.data[DATA_MANAGER]
    assert not manager.backup_agents


@pytest.mark.parametrize("service_data", [None, {}, {"password": "abc123"}])
async def test_create_service(
    hass: HomeAssistant,
    service_data: dict[str, Any] | None,
) -> None:
    """Test generate backup."""
    await setup_backup_integration(hass)

    with patch(
        "homeassistant.components.backup.manager.BackupManager.async_create_backup",
    ) as generate_backup:
        await hass.services.async_call(
            DOMAIN,
            "create",
            blocking=True,
            service_data=service_data,
        )

    assert generate_backup.called
