"""Tests for Shelly update platform."""

from unittest.mock import AsyncMock, Mock

from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.shelly.const import (
    DOMAIN,
    GEN1_RELEASE_URL,
    GEN2_BETA_RELEASE_URL,
    GEN2_RELEASE_URL,
)
from homeassistant.components.update import (
    ATTR_IN_PROGRESS,
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    ATTR_RELEASE_URL,
    ATTR_UPDATE_PERCENTAGE,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
    UpdateEntityFeature,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from . import (
    init_integration,
    inject_rpc_device_event,
    mock_rest_update,
    register_device,
    register_entity,
)

from tests.common import mock_restore_cache


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_block_update(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_block_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test block device update entity."""
    entity_id = "update.test_name_firmware"
    monkeypatch.setitem(mock_block_device.status["update"], "old_version", "1.0.0")
    monkeypatch.setitem(mock_block_device.status["update"], "new_version", "2.0.0")
    monkeypatch.setitem(mock_block_device.status, "cloud", {"connected": False})
    await init_integration(hass, 1)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.0.0"
    assert state.attributes[ATTR_LATEST_VERSION] == "2.0.0"
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] is None
    assert (
        state.attributes[ATTR_SUPPORTED_FEATURES]
        == UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert mock_block_device.trigger_ota_update.call_count == 1

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.0.0"
    assert state.attributes[ATTR_LATEST_VERSION] == "2.0.0"
    assert state.attributes[ATTR_IN_PROGRESS] is True
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] is None
    assert state.attributes[ATTR_RELEASE_URL] == GEN1_RELEASE_URL

    monkeypatch.setitem(mock_block_device.status["update"], "old_version", "2.0.0")
    await mock_rest_update(hass, freezer)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "2.0.0"
    assert state.attributes[ATTR_LATEST_VERSION] == "2.0.0"
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] is None

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-fwupdate"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_block_beta_update(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_block_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test block device beta update entity."""
    entity_id = "update.test_name_beta_firmware"
    monkeypatch.setitem(mock_block_device.status["update"], "old_version", "1.0.0")
    monkeypatch.setitem(mock_block_device.status["update"], "new_version", "2.0.0")
    monkeypatch.setitem(mock_block_device.status["update"], "beta_version", "")
    monkeypatch.setitem(mock_block_device.status, "cloud", {"connected": False})
    await init_integration(hass, 1)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.0.0"
    assert state.attributes[ATTR_LATEST_VERSION] == "1.0.0"
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] is None

    monkeypatch.setitem(
        mock_block_device.status["update"], "beta_version", "2.0.0-beta"
    )
    await mock_rest_update(hass, freezer)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.0.0"
    assert state.attributes[ATTR_LATEST_VERSION] == "2.0.0-beta"
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] is None
    assert state.attributes[ATTR_RELEASE_URL] is None

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert mock_block_device.trigger_ota_update.call_count == 1

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.0.0"
    assert state.attributes[ATTR_LATEST_VERSION] == "2.0.0-beta"
    assert state.attributes[ATTR_IN_PROGRESS] is True
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] is None

    monkeypatch.setitem(mock_block_device.status["update"], "old_version", "2.0.0-beta")
    await mock_rest_update(hass, freezer)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "2.0.0-beta"
    assert state.attributes[ATTR_LATEST_VERSION] == "2.0.0-beta"
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] is None

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-fwupdate_beta"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_block_update_connection_error(
    hass: HomeAssistant,
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test block device update connection error."""
    monkeypatch.setitem(mock_block_device.status["update"], "old_version", "1.0.0")
    monkeypatch.setitem(mock_block_device.status["update"], "new_version", "2.0.0")
    monkeypatch.setattr(
        mock_block_device,
        "trigger_ota_update",
        AsyncMock(side_effect=DeviceConnectionError),
    )
    await init_integration(hass, 1)

    with pytest.raises(
        HomeAssistantError,
        match="Device communication error occurred while triggering OTA update for Test name",
    ):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: "update.test_name_firmware"},
            blocking=True,
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_block_update_auth_error(
    hass: HomeAssistant,
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test block device update authentication error."""
    monkeypatch.setitem(mock_block_device.status["update"], "old_version", "1.0.0")
    monkeypatch.setitem(mock_block_device.status["update"], "new_version", "2.0.0")
    monkeypatch.setattr(
        mock_block_device,
        "trigger_ota_update",
        AsyncMock(side_effect=InvalidAuthError),
    )
    entry = await init_integration(hass, 1)

    assert entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.test_name_firmware"},
        blocking=True,
    )

    assert entry.state is ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_block_version_compare(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_block_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test block device custom firmware version comparison."""

    STABLE = "20230913-111730/v1.14.0-gcb84623"
    BETA = "20231107-162609/v1.14.1-rc1-g0617c15"

    entity_id_beta = "update.test_name_beta_firmware"
    entity_id_latest = "update.test_name_firmware"
    monkeypatch.setitem(mock_block_device.status["update"], "old_version", STABLE)
    monkeypatch.setitem(mock_block_device.status["update"], "new_version", "")
    monkeypatch.setitem(mock_block_device.status["update"], "beta_version", BETA)
    monkeypatch.setitem(mock_block_device.status, "cloud", {"connected": False})
    await init_integration(hass, 1)

    assert (state := hass.states.get(entity_id_latest))
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == STABLE
    assert state.attributes[ATTR_LATEST_VERSION] == STABLE

    assert (state := hass.states.get(entity_id_beta))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == STABLE
    assert state.attributes[ATTR_LATEST_VERSION] == BETA

    monkeypatch.setitem(mock_block_device.status["update"], "old_version", BETA)
    monkeypatch.setitem(mock_block_device.status["update"], "new_version", STABLE)
    monkeypatch.setitem(mock_block_device.status["update"], "beta_version", BETA)
    await mock_rest_update(hass, freezer)

    assert (state := hass.states.get(entity_id_latest))
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == BETA
    assert state.attributes[ATTR_LATEST_VERSION] == STABLE

    assert (state := hass.states.get(entity_id_beta))
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == BETA
    assert state.attributes[ATTR_LATEST_VERSION] == BETA


async def test_rpc_update(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC device update entity."""
    entity_id = "update.test_name_firmware"
    monkeypatch.setitem(mock_rpc_device.shelly, "ver", "1")
    monkeypatch.setitem(
        mock_rpc_device.status["sys"],
        "available_updates",
        {
            "stable": {"version": "2"},
        },
    )
    await init_integration(hass, 2)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2"
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] is None
    supported_feat = state.attributes[ATTR_SUPPORTED_FEATURES]
    assert supported_feat == UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert mock_rpc_device.trigger_ota_update.call_count == 1

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2"
    assert state.attributes[ATTR_IN_PROGRESS] is True
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] is None
    assert state.attributes[ATTR_RELEASE_URL] == GEN2_RELEASE_URL

    inject_rpc_device_event(
        monkeypatch,
        mock_rpc_device,
        {
            "events": [
                {
                    "event": "ota_begin",
                    "id": 1,
                    "ts": 1668522399.2,
                }
            ],
            "ts": 1668522399.2,
        },
    )

    assert (state := hass.states.get(entity_id))
    assert state.attributes[ATTR_IN_PROGRESS] is True
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] == 0

    inject_rpc_device_event(
        monkeypatch,
        mock_rpc_device,
        {
            "events": [
                {
                    "event": "ota_progress",
                    "id": 1,
                    "ts": 1668522399.2,
                    "progress_percent": 50,
                }
            ],
            "ts": 1668522399.2,
        },
    )

    assert (state := hass.states.get(entity_id))
    assert state.attributes[ATTR_IN_PROGRESS] is True
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] == 50

    inject_rpc_device_event(
        monkeypatch,
        mock_rpc_device,
        {
            "events": [
                {
                    "event": "ota_success",
                    "id": 1,
                    "ts": 1668522399.2,
                }
            ],
            "ts": 1668522399.2,
        },
    )
    monkeypatch.setitem(mock_rpc_device.shelly, "ver", "2")
    mock_rpc_device.mock_update()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "2"
    assert state.attributes[ATTR_LATEST_VERSION] == "2"
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] is None

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-sys-fwupdate"


async def test_rpc_sleeping_update(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC sleeping device update entity."""
    monkeypatch.setattr(mock_rpc_device, "connected", False)
    monkeypatch.setitem(mock_rpc_device.status["sys"], "wakeup_period", 1000)
    monkeypatch.setitem(mock_rpc_device.shelly, "ver", "1")
    monkeypatch.setitem(
        mock_rpc_device.status["sys"],
        "available_updates",
        {
            "stable": {"version": "2"},
        },
    )
    entity_id = f"{UPDATE_DOMAIN}.test_name_firmware"
    await init_integration(hass, 2, sleep_period=1000)

    # Entity should be created when device is online
    assert hass.states.get(entity_id) is None

    # Make device online
    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2"
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] is None
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == UpdateEntityFeature(0)
    assert state.attributes[ATTR_RELEASE_URL] == GEN2_RELEASE_URL

    monkeypatch.setitem(mock_rpc_device.shelly, "ver", "2")
    mock_rpc_device.mock_update()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "2"
    assert state.attributes[ATTR_LATEST_VERSION] == "2"
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] is None
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == UpdateEntityFeature(0)

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-sys-fwupdate"


async def test_rpc_restored_sleeping_update(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    device_registry: DeviceRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC restored update entity."""
    entry = await init_integration(hass, 2, sleep_period=1000, skip_setup=True)
    device = register_device(device_registry, entry)
    entity_id = register_entity(
        hass,
        UPDATE_DOMAIN,
        "test_name_firmware",
        "sys-fwupdate",
        entry,
        device_id=device.id,
    )

    attr = {ATTR_INSTALLED_VERSION: "1", ATTR_LATEST_VERSION: "2"}
    mock_restore_cache(hass, [State(entity_id, STATE_ON, attributes=attr)])
    monkeypatch.setitem(mock_rpc_device.shelly, "ver", "2")
    monkeypatch.setitem(mock_rpc_device.status["sys"], "available_updates", {})
    monkeypatch.setattr(mock_rpc_device, "initialized", False)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2"
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] is None
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == UpdateEntityFeature(0)

    # Make device online
    monkeypatch.setattr(mock_rpc_device, "initialized", True)
    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    # Mock update
    mock_rpc_device.mock_update()
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "2"
    assert state.attributes[ATTR_LATEST_VERSION] == "2"
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] is None
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == UpdateEntityFeature(0)


async def test_rpc_restored_sleeping_update_no_last_state(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    device_registry: DeviceRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC restored update entity missing last state."""
    monkeypatch.setitem(mock_rpc_device.shelly, "ver", "1")
    monkeypatch.setitem(
        mock_rpc_device.status["sys"],
        "available_updates",
        {
            "stable": {"version": "2"},
        },
    )
    entry = await init_integration(hass, 2, sleep_period=1000, skip_setup=True)
    device = register_device(device_registry, entry)
    entity_id = register_entity(
        hass,
        UPDATE_DOMAIN,
        "test_name_firmware",
        "sys-fwupdate",
        entry,
        device_id=device.id,
    )

    monkeypatch.setattr(mock_rpc_device, "initialized", False)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNKNOWN

    # Make device online
    monkeypatch.setattr(mock_rpc_device, "initialized", True)
    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    # Mock update
    mock_rpc_device.mock_update()
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2"
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] is None
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == UpdateEntityFeature(0)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_rpc_beta_update(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC device beta update entity."""
    entity_id = "update.test_name_beta_firmware"
    monkeypatch.setitem(mock_rpc_device.shelly, "ver", "1")
    monkeypatch.setitem(
        mock_rpc_device.status["sys"],
        "available_updates",
        {
            "stable": {"version": "2"},
            "beta": {"version": ""},
        },
    )
    await init_integration(hass, 2)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "1"
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] is None

    monkeypatch.setitem(
        mock_rpc_device.status["sys"],
        "available_updates",
        {
            "stable": {"version": "2"},
            "beta": {"version": "2b"},
        },
    )
    await mock_rest_update(hass, freezer)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2b"
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_RELEASE_URL] == GEN2_BETA_RELEASE_URL

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    inject_rpc_device_event(
        monkeypatch,
        mock_rpc_device,
        {
            "events": [
                {
                    "event": "ota_begin",
                    "id": 1,
                    "ts": 1668522399.2,
                }
            ],
            "ts": 1668522399.2,
        },
    )

    assert mock_rpc_device.trigger_ota_update.call_count == 1

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2b"
    assert state.attributes[ATTR_IN_PROGRESS] is True
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] == 0

    inject_rpc_device_event(
        monkeypatch,
        mock_rpc_device,
        {
            "events": [
                {
                    "event": "ota_progress",
                    "id": 1,
                    "ts": 1668522399.2,
                    "progress_percent": 40,
                }
            ],
            "ts": 1668522399.2,
        },
    )

    assert (state := hass.states.get(entity_id))
    assert state.attributes[ATTR_IN_PROGRESS] is True
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] == 40

    inject_rpc_device_event(
        monkeypatch,
        mock_rpc_device,
        {
            "events": [
                {
                    "event": "ota_success",
                    "id": 1,
                    "ts": 1668522399.2,
                }
            ],
            "ts": 1668522399.2,
        },
    )
    monkeypatch.setitem(mock_rpc_device.shelly, "ver", "2b")
    await mock_rest_update(hass, freezer)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "2b"
    assert state.attributes[ATTR_LATEST_VERSION] == "2b"
    assert state.attributes[ATTR_IN_PROGRESS] is False
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] is None

    assert (entry := entity_registry.async_get(entity_id))
    assert entry.unique_id == "123456789ABC-sys-fwupdate_beta"


@pytest.mark.parametrize(
    ("exc", "error"),
    [
        (
            DeviceConnectionError,
            "Device communication error occurred while triggering OTA update for Test name",
        ),
        (
            RpcCallError(-1, "error"),
            "RPC call error occurred while triggering OTA update for Test name",
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_rpc_update_errors(
    hass: HomeAssistant,
    exc: Exception,
    error: str,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test RPC device update connection/call errors."""
    monkeypatch.setitem(mock_rpc_device.shelly, "ver", "1")
    monkeypatch.setitem(
        mock_rpc_device.status["sys"],
        "available_updates",
        {
            "stable": {"version": "2"},
            "beta": {"version": ""},
        },
    )
    monkeypatch.setattr(
        mock_rpc_device, "trigger_ota_update", AsyncMock(side_effect=exc)
    )
    await init_integration(hass, 2)

    with pytest.raises(HomeAssistantError, match=error):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: "update.test_name_firmware"},
            blocking=True,
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_rpc_update_auth_error(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    entity_registry: EntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC device update authentication error."""
    monkeypatch.setitem(mock_rpc_device.shelly, "ver", "1")
    monkeypatch.setitem(
        mock_rpc_device.status["sys"],
        "available_updates",
        {
            "stable": {"version": "2"},
            "beta": {"version": ""},
        },
    )
    monkeypatch.setattr(
        mock_rpc_device,
        "trigger_ota_update",
        AsyncMock(side_effect=InvalidAuthError),
    )
    entry = await init_integration(hass, 2)

    assert entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.test_name_firmware"},
        blocking=True,
    )

    assert entry.state is ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id
