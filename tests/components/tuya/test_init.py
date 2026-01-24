"""Test Tuya initialization."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.tuya.const import (
    CONF_DP_CODE,
    CONF_DP_VALUE,
    DOMAIN,
    SERVICE_SET_DP_VALUE,
)
from homeassistant.components.tuya.diagnostics import _REDACTED_DPCODES
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import DEVICE_MOCKS, initialize_entry

from tests.common import MockConfigEntry, async_load_json_object_fixture


async def test_device_registry(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_devices: CustomerDevice,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Validate device registry snapshots for all devices, including unsupported ones."""

    await initialize_entry(hass, mock_manager, mock_config_entry, mock_devices)

    device_registry_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )

    # Ensure the device registry contains same amount as DEVICE_MOCKS
    assert len(device_registry_entries) == len(DEVICE_MOCKS)

    for device_registry_entry in device_registry_entries:
        assert device_registry_entry == snapshot(
            name=list(device_registry_entry.identifiers)[0][1]
        )

        # Ensure model is suffixed with "(unsupported)" when no entities are generated
        assert (" (unsupported)" in device_registry_entry.model) == (
            not er.async_entries_for_device(
                entity_registry,
                device_registry_entry.id,
                include_disabled_entities=True,
            )
        )


async def test_fixtures_valid(hass: HomeAssistant) -> None:
    """Ensure Tuya fixture files are valid."""
    # We want to ensure that the fixture files do not contain
    # `home_assistant`, `id`, or `terminal_id` keys.
    # These are provided by the Tuya diagnostics and should be removed
    # from the fixture.
    EXCLUDE_KEYS = ("home_assistant", "id", "terminal_id")

    for device_code in DEVICE_MOCKS:
        details = await async_load_json_object_fixture(
            hass, f"{device_code}.json", DOMAIN
        )
        for key in EXCLUDE_KEYS:
            assert key not in details, (
                f"Please remove data[`'{key}']` from {device_code}.json"
            )
        if "status" in details:
            statuses = details["status"]
            for key in statuses:
                if key in _REDACTED_DPCODES:
                    assert statuses[key] == "**REDACTED**", (
                        f"Please mark `data['status']['{key}']` as `**REDACTED**`"
                        f" in {device_code}.json"
                    )


@pytest.mark.parametrize("mock_device_code", ["cz_0fHWRe8ULjtmnBNd"])
async def test_service_set_dp_value(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the set_dp_value service."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    # Verify service is registered
    assert hass.services.has_service(DOMAIN, SERVICE_SET_DP_VALUE)

    # Get device registry entry
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_device.id)}
    )
    assert device_entry is not None

    # Test with HA device ID
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_DP_VALUE,
        {
            CONF_DEVICE_ID: device_entry.id,
            CONF_DP_CODE: "switch_1",
            CONF_DP_VALUE: True,
        },
        blocking=True,
    )
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id,
        [{"code": "switch_1", "value": True}],
    )

    # Reset mock
    mock_manager.send_commands.reset_mock()

    # Test with Tuya device ID directly
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_DP_VALUE,
        {
            CONF_DEVICE_ID: mock_device.id,
            CONF_DP_CODE: "switch_1",
            CONF_DP_VALUE: False,
        },
        blocking=True,
    )
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id,
        [{"code": "switch_1", "value": False}],
    )


@pytest.mark.parametrize("mock_device_code", ["cz_0fHWRe8ULjtmnBNd"])
async def test_service_set_dp_value_device_not_found(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test the set_dp_value service with invalid device ID."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_DP_VALUE,
            {
                CONF_DEVICE_ID: "invalid_device_id",
                CONF_DP_CODE: "switch_1",
                CONF_DP_VALUE: True,
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "device_not_found"


@pytest.mark.parametrize("mock_device_code", ["cz_0fHWRe8ULjtmnBNd"])
async def test_service_set_dp_value_device_offline(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test the set_dp_value service with offline device."""
    mock_device.online = False
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_DP_VALUE,
            {
                CONF_DEVICE_ID: mock_device.id,
                CONF_DP_CODE: "switch_1",
                CONF_DP_VALUE: True,
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "device_offline"


@pytest.mark.parametrize("mock_device_code", ["cz_0fHWRe8ULjtmnBNd"])
async def test_service_set_dp_value_invalid_dp_code(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test the set_dp_value service with invalid DP code."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_DP_VALUE,
            {
                CONF_DEVICE_ID: mock_device.id,
                CONF_DP_CODE: "invalid_dp_code",
                CONF_DP_VALUE: True,
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "invalid_dp_code"


@pytest.mark.parametrize("mock_device_code", ["cz_0fHWRe8ULjtmnBNd"])
async def test_service_set_dp_value_empty_function(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test the set_dp_value service with device that has no functions."""
    mock_device.function = {}
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_DP_VALUE,
            {
                CONF_DEVICE_ID: mock_device.id,
                CONF_DP_CODE: "switch_1",
                CONF_DP_VALUE: True,
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "invalid_dp_code"


@pytest.mark.parametrize("mock_device_code", ["cz_0fHWRe8ULjtmnBNd"])
async def test_service_set_dp_value_send_command_failed(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test the set_dp_value service when send_commands fails."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    mock_manager.send_commands.side_effect = Exception("Connection failed")

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_DP_VALUE,
            {
                CONF_DEVICE_ID: mock_device.id,
                CONF_DP_CODE: "switch_1",
                CONF_DP_VALUE: True,
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "send_command_failed"


@pytest.mark.parametrize("mock_device_code", ["cz_0fHWRe8ULjtmnBNd"])
async def test_service_unregistered_on_last_entry_unload(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test that service is unregistered when last config entry is unloaded."""
    mock_manager.device_map = {mock_device.id: mock_device}
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.tuya.Manager", return_value=mock_manager):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Service should be registered
    assert hass.services.has_service(DOMAIN, SERVICE_SET_DP_VALUE)

    # Unload the entry
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Service should be unregistered
    assert not hass.services.has_service(DOMAIN, SERVICE_SET_DP_VALUE)
