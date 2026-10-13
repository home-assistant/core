"""Tests for the Mikrotik update platform."""

from copy import deepcopy
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN, SERVICE_INSTALL
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_mikrotik_entry
from .const import ROUTERBOARD_DATA, TEST_FIRMWARE, TEST_INSTALLED_VERSION, UPDATE_DATA

from tests.common import snapshot_platform

FW_UPDATE_ENTITY_ID = "update.mikrotik_routeros"
ROUTERBOARD_UPDATE_ENTITY_ID = "update.mikrotik_routerboard"


@pytest.mark.parametrize(
    "setup_kwargs",
    [
        pytest.param({}, id="no_update"),
        pytest.param(UPDATE_DATA[0], id="firmware_update_available"),
        pytest.param(ROUTERBOARD_DATA[0], id="routerboard_update_available"),
    ],
)
async def test_update_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_kwargs: dict[str, Any],
) -> None:
    """Test Mikrotik update entities are created with expected values."""
    with patch("homeassistant.components.mikrotik.PLATFORMS", [Platform.UPDATE]):
        config_entry = await setup_mikrotik_entry(hass, **setup_kwargs)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("setup_kwargs", "entity_id", "expected_command"),
    [
        pytest.param(
            UPDATE_DATA[0],
            FW_UPDATE_ENTITY_ID,
            "/system/package/update/install",
            id="firmware",
        ),
        pytest.param(
            ROUTERBOARD_DATA[0],
            ROUTERBOARD_UPDATE_ENTITY_ID,
            "/system/routerboard/upgrade",
            id="routerboard",
        ),
    ],
)
async def test_update_install(
    hass: HomeAssistant,
    mock_api: MagicMock,
    setup_kwargs: dict[str, Any],
    entity_id: str,
    expected_command: str,
) -> None:
    """Test installing a Mikrotik firmware update."""
    await setup_mikrotik_entry(hass, **setup_kwargs)

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_api.assert_called_with(expected_command)


async def test_firmware_update_install_with_backup(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Test installing a RouterOS firmware update with a backup beforehand."""
    await setup_mikrotik_entry(hass, **UPDATE_DATA[0])

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: FW_UPDATE_ENTITY_ID, "backup": True},
        blocking=True,
    )

    assert mock_api.call_args_list[-2].args == ("/system/backup/save",)
    assert mock_api.call_args_list[-1].args == ("/system/package/update/install",)


@pytest.mark.parametrize(
    ("entity_id", "expected_version"),
    [
        pytest.param(FW_UPDATE_ENTITY_ID, TEST_INSTALLED_VERSION, id="firmware"),
        pytest.param(ROUTERBOARD_UPDATE_ENTITY_ID, TEST_FIRMWARE, id="routerboard"),
    ],
)
async def test_no_update_available(
    hass: HomeAssistant, entity_id: str, expected_version: str
) -> None:
    """Test update entities report no update available by default."""
    update_data = deepcopy(UPDATE_DATA[0])
    update_data.pop("latest-version", None)

    routerboard_data = deepcopy(ROUTERBOARD_DATA[0])
    routerboard_data.pop("upgrade-firmware", None)

    await setup_mikrotik_entry(
        hass,
        update_data=[update_data],
        routerboard_data=[routerboard_data],
    )

    assert (state := hass.states.get(entity_id))
    assert state.attributes["installed_version"] == expected_version
    assert state.attributes["latest_version"] == expected_version
    assert state.state == STATE_OFF
