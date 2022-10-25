"""Tests for Shelly update platform."""
from datetime import timedelta
from unittest.mock import AsyncMock

from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError, RpcCallError
import pytest

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.shelly.const import DOMAIN, REST_SENSORS_UPDATE_INTERVAL
from homeassistant.components.update import (
    ATTR_IN_PROGRESS,
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_registry import async_get
from homeassistant.util import dt

from . import MOCK_MAC, init_integration

from tests.common import async_fire_time_changed


@pytest.mark.parametrize(
    "gen, domain, unique_id, object_id",
    [
        (1, BINARY_SENSOR_DOMAIN, f"{MOCK_MAC}-fwupdate", "firmware_update"),
        (1, BUTTON_DOMAIN, "test_name_ota_update", "ota_update"),
        (1, BUTTON_DOMAIN, "test_name_ota_update_beta", "ota_update_beta"),
        (2, BINARY_SENSOR_DOMAIN, f"{MOCK_MAC}-sys-fwupdate", "firmware_update"),
        (2, BUTTON_DOMAIN, "test_name_ota_update", "ota_update"),
        (2, BUTTON_DOMAIN, "test_name_ota_update_beta", "ota_update_beta"),
    ],
)
async def test_remove_legacy_entities(
    hass: HomeAssistant,
    gen,
    domain,
    unique_id,
    object_id,
    mock_block_device,
    mock_rpc_device,
):
    """Test removes legacy update entities."""
    entity_id = f"{domain}.test_name_{object_id}"
    entity_registry = async_get(hass)
    entity_registry.async_get_or_create(
        domain,
        DOMAIN,
        unique_id,
        suggested_object_id=f"test_name_{object_id}",
        disabled_by=None,
    )

    assert entity_registry.async_get(entity_id) is not None

    await init_integration(hass, gen)

    assert entity_registry.async_get(entity_id) is None


async def test_block_update(hass: HomeAssistant, mock_block_device, monkeypatch):
    """Test block device update entity."""
    entity_registry = async_get(hass)
    entity_registry.async_get_or_create(
        UPDATE_DOMAIN,
        DOMAIN,
        f"{MOCK_MAC}-fwupdate",
        suggested_object_id="test_name_firmware_update",
        disabled_by=None,
    )
    monkeypatch.setitem(mock_block_device.status["update"], "old_version", "1")
    monkeypatch.setitem(mock_block_device.status["update"], "new_version", "2")
    await init_integration(hass, 1)

    state = hass.states.get("update.test_name_firmware_update")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2"
    assert state.attributes[ATTR_IN_PROGRESS] is False

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.test_name_firmware_update"},
        blocking=True,
    )
    assert mock_block_device.trigger_ota_update.call_count == 1

    state = hass.states.get("update.test_name_firmware_update")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2"
    assert state.attributes[ATTR_IN_PROGRESS] is True

    monkeypatch.setitem(mock_block_device.status["update"], "old_version", "2")
    async_fire_time_changed(
        hass, dt.utcnow() + timedelta(seconds=REST_SENSORS_UPDATE_INTERVAL)
    )
    await hass.async_block_till_done()

    state = hass.states.get("update.test_name_firmware_update")
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "2"
    assert state.attributes[ATTR_LATEST_VERSION] == "2"
    assert state.attributes[ATTR_IN_PROGRESS] is False


async def test_block_beta_update(hass: HomeAssistant, mock_block_device, monkeypatch):
    """Test block device beta update entity."""
    entity_registry = async_get(hass)
    entity_registry.async_get_or_create(
        UPDATE_DOMAIN,
        DOMAIN,
        f"{MOCK_MAC}-fwupdate_beta",
        suggested_object_id="test_name_beta_firmware_update",
        disabled_by=None,
    )
    monkeypatch.setitem(mock_block_device.status["update"], "old_version", "1")
    monkeypatch.setitem(mock_block_device.status["update"], "new_version", "2")
    monkeypatch.setitem(mock_block_device.status["update"], "beta_version", "")
    await init_integration(hass, 1)

    state = hass.states.get("update.test_name_beta_firmware_update")
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "1"
    assert state.attributes[ATTR_IN_PROGRESS] is False

    monkeypatch.setitem(mock_block_device.status["update"], "beta_version", "2b")
    async_fire_time_changed(
        hass, dt.utcnow() + timedelta(seconds=REST_SENSORS_UPDATE_INTERVAL)
    )
    await hass.async_block_till_done()

    state = hass.states.get("update.test_name_beta_firmware_update")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2b"
    assert state.attributes[ATTR_IN_PROGRESS] is False

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.test_name_beta_firmware_update"},
        blocking=True,
    )
    assert mock_block_device.trigger_ota_update.call_count == 1

    state = hass.states.get("update.test_name_beta_firmware_update")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2b"
    assert state.attributes[ATTR_IN_PROGRESS] is True

    monkeypatch.setitem(mock_block_device.status["update"], "old_version", "2b")
    async_fire_time_changed(
        hass, dt.utcnow() + timedelta(seconds=REST_SENSORS_UPDATE_INTERVAL)
    )
    await hass.async_block_till_done()

    state = hass.states.get("update.test_name_beta_firmware_update")
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "2b"
    assert state.attributes[ATTR_LATEST_VERSION] == "2b"
    assert state.attributes[ATTR_IN_PROGRESS] is False


async def test_block_update_connection_error(
    hass: HomeAssistant, mock_block_device, monkeypatch, caplog
):
    """Test block device update connection error."""
    entity_registry = async_get(hass)
    entity_registry.async_get_or_create(
        UPDATE_DOMAIN,
        DOMAIN,
        f"{MOCK_MAC}-fwupdate",
        suggested_object_id="test_name_firmware_update",
        disabled_by=None,
    )
    monkeypatch.setitem(mock_block_device.status["update"], "old_version", "1")
    monkeypatch.setitem(mock_block_device.status["update"], "new_version", "2")
    monkeypatch.setattr(
        mock_block_device,
        "trigger_ota_update",
        AsyncMock(side_effect=DeviceConnectionError),
    )
    await init_integration(hass, 1)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: "update.test_name_firmware_update"},
            blocking=True,
        )
        assert "Error starting OTA update" in caplog.text


async def test_block_update_auth_error(
    hass: HomeAssistant, mock_block_device, monkeypatch
):
    """Test block device update authentication error."""
    entity_registry = async_get(hass)
    entity_registry.async_get_or_create(
        UPDATE_DOMAIN,
        DOMAIN,
        f"{MOCK_MAC}-fwupdate",
        suggested_object_id="test_name_firmware_update",
        disabled_by=None,
    )
    monkeypatch.setitem(mock_block_device.status["update"], "old_version", "1")
    monkeypatch.setitem(mock_block_device.status["update"], "new_version", "2")
    monkeypatch.setattr(
        mock_block_device,
        "trigger_ota_update",
        AsyncMock(side_effect=InvalidAuthError),
    )
    entry = await init_integration(hass, 1)

    assert entry.state == ConfigEntryState.LOADED

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.test_name_firmware_update"},
        blocking=True,
    )

    assert entry.state == ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id


async def test_rpc_update(hass: HomeAssistant, mock_rpc_device, monkeypatch):
    """Test RPC device update entity."""
    entity_registry = async_get(hass)
    entity_registry.async_get_or_create(
        UPDATE_DOMAIN,
        DOMAIN,
        f"{MOCK_MAC}-sys-fwupdate",
        suggested_object_id="test_name_firmware_update",
        disabled_by=None,
    )
    monkeypatch.setitem(mock_rpc_device.shelly, "ver", "1")
    monkeypatch.setitem(
        mock_rpc_device.status["sys"],
        "available_updates",
        {
            "stable": {"version": "2"},
        },
    )
    await init_integration(hass, 2)

    state = hass.states.get("update.test_name_firmware_update")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2"
    assert state.attributes[ATTR_IN_PROGRESS] is False

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.test_name_firmware_update"},
        blocking=True,
    )
    assert mock_rpc_device.trigger_ota_update.call_count == 1

    state = hass.states.get("update.test_name_firmware_update")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2"
    assert state.attributes[ATTR_IN_PROGRESS] is True

    monkeypatch.setitem(mock_rpc_device.shelly, "ver", "2")
    async_fire_time_changed(
        hass, dt.utcnow() + timedelta(seconds=REST_SENSORS_UPDATE_INTERVAL)
    )
    await hass.async_block_till_done()

    state = hass.states.get("update.test_name_firmware_update")
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "2"
    assert state.attributes[ATTR_LATEST_VERSION] == "2"
    assert state.attributes[ATTR_IN_PROGRESS] is False


async def test_rpc_beta_update(hass: HomeAssistant, mock_rpc_device, monkeypatch):
    """Test RPC device beta update entity."""
    entity_registry = async_get(hass)
    entity_registry.async_get_or_create(
        UPDATE_DOMAIN,
        DOMAIN,
        f"{MOCK_MAC}-sys-fwupdate_beta",
        suggested_object_id="test_name_beta_firmware_update",
        disabled_by=None,
    )
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

    state = hass.states.get("update.test_name_beta_firmware_update")
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "1"
    assert state.attributes[ATTR_IN_PROGRESS] is False

    monkeypatch.setitem(
        mock_rpc_device.status["sys"],
        "available_updates",
        {
            "stable": {"version": "2"},
            "beta": {"version": "2b"},
        },
    )
    async_fire_time_changed(
        hass, dt.utcnow() + timedelta(seconds=REST_SENSORS_UPDATE_INTERVAL)
    )
    await hass.async_block_till_done()

    state = hass.states.get("update.test_name_beta_firmware_update")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2b"
    assert state.attributes[ATTR_IN_PROGRESS] is False

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.test_name_beta_firmware_update"},
        blocking=True,
    )
    assert mock_rpc_device.trigger_ota_update.call_count == 1

    state = hass.states.get("update.test_name_beta_firmware_update")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1"
    assert state.attributes[ATTR_LATEST_VERSION] == "2b"
    assert state.attributes[ATTR_IN_PROGRESS] is True

    monkeypatch.setitem(mock_rpc_device.shelly, "ver", "2b")
    async_fire_time_changed(
        hass, dt.utcnow() + timedelta(seconds=REST_SENSORS_UPDATE_INTERVAL)
    )
    await hass.async_block_till_done()

    state = hass.states.get("update.test_name_beta_firmware_update")
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "2b"
    assert state.attributes[ATTR_LATEST_VERSION] == "2b"
    assert state.attributes[ATTR_IN_PROGRESS] is False


@pytest.mark.parametrize(
    "exc, error",
    [
        (DeviceConnectionError, "Error starting OTA update"),
        (RpcCallError(-1, "error"), "OTA update request error"),
    ],
)
async def test_rpc_update__errors(
    hass: HomeAssistant, exc, error, mock_rpc_device, monkeypatch, caplog
):
    """Test RPC device update connection/call errors."""
    entity_registry = async_get(hass)
    entity_registry.async_get_or_create(
        UPDATE_DOMAIN,
        DOMAIN,
        f"{MOCK_MAC}-sys-fwupdate",
        suggested_object_id="test_name_firmware_update",
        disabled_by=None,
    )
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

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: "update.test_name_firmware_update"},
            blocking=True,
        )
        assert error in caplog.text


async def test_rpc_update_auth_error(
    hass: HomeAssistant, mock_rpc_device, monkeypatch, caplog
):
    """Test RPC device update authentication error."""
    entity_registry = async_get(hass)
    entity_registry.async_get_or_create(
        UPDATE_DOMAIN,
        DOMAIN,
        f"{MOCK_MAC}-sys-fwupdate",
        suggested_object_id="test_name_firmware_update",
        disabled_by=None,
    )
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

    assert entry.state == ConfigEntryState.LOADED

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.test_name_firmware_update"},
        blocking=True,
    )

    assert entry.state == ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id
