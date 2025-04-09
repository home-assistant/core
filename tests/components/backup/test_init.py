"""Tests for the Backup integration."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.backup.const import DATA_MANAGER, DOMAIN
from homeassistant.config_entries import SOURCE_SYSTEM, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceNotFound

from .common import setup_backup_integration

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


@pytest.mark.usefixtures("supervisor_client")
async def test_setup_with_hassio(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the setup of the integration with hassio enabled."""
    await setup_backup_integration(hass=hass, with_hassio=True)
    manager = hass.data[DATA_MANAGER]
    assert not manager.backup_agents


@pytest.mark.parametrize("service_data", [None, {}])
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

    generate_backup.assert_called_once_with(
        agent_ids=["backup.local"],
        include_addons=None,
        include_all_addons=False,
        include_database=True,
        include_folders=None,
        include_homeassistant=True,
        name=None,
        password=None,
    )


@pytest.mark.usefixtures("supervisor_client")
async def test_create_service_with_hassio(hass: HomeAssistant) -> None:
    """Test action backup.create does not exist with hassio."""
    await setup_backup_integration(hass, with_hassio=True)

    with pytest.raises(ServiceNotFound):
        await hass.services.async_call(DOMAIN, "create", blocking=True)


@pytest.mark.parametrize(
    ("commands", "expected_kwargs"),
    [
        (
            [],
            {
                "agent_ids": [],
                "include_addons": None,
                "include_all_addons": False,
                "include_database": True,
                "include_folders": None,
                "include_homeassistant": True,
                "name": None,
                "password": None,
                "with_automatic_settings": True,
            },
        ),
        (
            [
                {
                    "type": "backup/config/update",
                    "create_backup": {
                        "agent_ids": ["test-agent"],
                        "include_addons": ["my-addon"],
                        "include_all_addons": True,
                        "include_database": False,
                        "include_folders": ["share"],
                        "name": "cool_backup",
                        "password": "hunter2",
                    },
                },
            ],
            {
                "agent_ids": ["test-agent"],
                "include_addons": ["my-addon"],
                "include_all_addons": True,
                "include_database": False,
                "include_folders": ["share"],
                "include_homeassistant": True,
                "name": "cool_backup",
                "password": "hunter2",
                "with_automatic_settings": True,
            },
        ),
    ],
)
@pytest.mark.parametrize("service_data", [None, {}])
@pytest.mark.parametrize("with_hassio", [True, False])
@pytest.mark.usefixtures("supervisor_client")
async def test_create_automatic_service(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    commands: list[dict[str, Any]],
    expected_kwargs: dict[str, Any],
    service_data: dict[str, Any] | None,
    with_hassio: bool,
) -> None:
    """Test generate backup."""
    await setup_backup_integration(hass, with_hassio=with_hassio)

    client = await hass_ws_client(hass)
    for command in commands:
        await client.send_json_auto_id(command)
        result = await client.receive_json()
        assert result["success"]

    with patch(
        "homeassistant.components.backup.manager.BackupManager.async_create_backup",
    ) as generate_backup:
        await hass.services.async_call(
            DOMAIN,
            "create_automatic",
            blocking=True,
            service_data=service_data,
        )

    generate_backup.assert_called_once_with(**expected_kwargs)


async def test_setup_entry(
    hass: HomeAssistant,
) -> None:
    """Test setup backup config entry."""
    await setup_backup_integration(hass, with_hassio=False)
    entry = MockConfigEntry(domain=DOMAIN, source=SOURCE_SYSTEM)
    entry.add_to_hass(hass)

    with patch("homeassistant.components.backup.PLATFORMS", return_value=[]):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
