"""Tests for Tuya services."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.tuya.const import DOMAIN
from homeassistant.components.tuya.service import async_register_services
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import initialize_entry

from tests.common import MockConfigEntry


@pytest.mark.parametrize("mock_device_code", ["bzyd_45idzfufidgee7ir"])
async def test_get_data_success(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test get_data service returns device status."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    await async_register_services(hass)

    with patch(
        "homeassistant.components.tuya.service._get_tuya_device",
        return_value=(mock_device, mock_manager),
    ):
        result = await hass.services.async_call(
            DOMAIN,
            "get_data",
            {"device_id": mock_device.id, "dp_code": "switch"},
            blocking=True,
            return_response=True,
        )

    assert result["data"] == mock_device.status["switch"]


@pytest.mark.parametrize("mock_device_code", ["bzyd_45idzfufidgee7ir"])
async def test_get_data_invalid_dp_code(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test get_data service with invalid DP code."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    await async_register_services(hass)

    with patch(
        "homeassistant.components.tuya.service._get_tuya_device",
        return_value=(mock_device, mock_manager),
    ):
        with pytest.raises(HomeAssistantError) as exc_info:
            await hass.services.async_call(
                DOMAIN,
                "get_data",
                {"device_id": mock_device.id, "dp_code": "999"},
                blocking=True,
                return_response=True,
            )
        assert "does not have data" in str(exc_info.value)


@pytest.mark.parametrize("mock_device_code", ["bzyd_45idzfufidgee7ir"])
async def test_set_data_success(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test set_data service sends command."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    await async_register_services(hass)

    with patch(
        "homeassistant.components.tuya.service._get_tuya_device",
        return_value=(mock_device, mock_manager),
    ):
        result = await hass.services.async_call(
            DOMAIN,
            "set_data",
            {"device_id": mock_device.id, "dp_code": "switch", "data": False},
            blocking=True,
            return_response=True,
        )

    assert result["success"] is True
    assert result["dp_code"] == "switch"
    assert result["value"] is False
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id, [{"code": "switch", "value": False}]
    )


@pytest.mark.parametrize("mock_device_code", ["bzyd_45idzfufidgee7ir"])
async def test_set_data_unsupported_dp_code(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test set_data service with unsupported DP code."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    await async_register_services(hass)

    with patch(
        "homeassistant.components.tuya.service._get_tuya_device",
        return_value=(mock_device, mock_manager),
    ):
        with pytest.raises(HomeAssistantError) as exc_info:
            await hass.services.async_call(
                DOMAIN,
                "set_data",
                {"device_id": mock_device.id, "dp_code": "999", "data": True},
                blocking=True,
                return_response=True,
            )
        assert "does not support DP code" in str(exc_info.value)


@pytest.mark.parametrize("mock_device_code", ["bzyd_45idzfufidgee7ir"])
@pytest.mark.parametrize(
    "data_value",
    [
        "string_value",
        42,
        3.14,
        True,
        {"nested": "dict"},
        [1, 2, 3],
    ],
)
async def test_set_data_various_data_types(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    data_value,
) -> None:
    """Test set_data service with various data types."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    await async_register_services(hass)

    with patch(
        "homeassistant.components.tuya.service._get_tuya_device",
        return_value=(mock_device, mock_manager),
    ):
        result = await hass.services.async_call(
            DOMAIN,
            "set_data",
            {"device_id": mock_device.id, "dp_code": "switch", "data": data_value},
            blocking=True,
            return_response=True,
        )

    assert result["value"] == data_value


@pytest.mark.parametrize("mock_device_code", ["bzyd_45idzfufidgee7ir"])
async def test_get_available_dp_codes_success(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test get_available_dp_codes service."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    await async_register_services(hass)

    with patch(
        "homeassistant.components.tuya.service._get_tuya_device",
        return_value=(mock_device, mock_manager),
    ):
        result = await hass.services.async_call(
            DOMAIN,
            "get_available_dp_codes",
            {"device_id": mock_device.id},
            blocking=True,
            return_response=True,
        )

    assert set(result["settable_codes"]) == set(mock_device.function.keys())
    assert set(result["readable_codes"]) == set(mock_device.status.keys())
    assert result["current_values"] == mock_device.status


async def test_device_not_found(hass: HomeAssistant) -> None:
    """Test service with non-existent device."""
    await async_register_services(hass)

    with (
        patch(
            "homeassistant.components.tuya.service._get_tuya_device",
            side_effect=HomeAssistantError("Device not found"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            "get_data",
            {"device_id": "invalid_device_id", "dp_code": "switch"},
            blocking=True,
            return_response=True,
        )
