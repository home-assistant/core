"""Test ESPHome update entities."""
import dataclasses
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.esphome.dashboard import async_get_dashboard
from homeassistant.components.update import UpdateEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send


@pytest.fixture(autouse=True)
def stub_reconnect():
    """Stub reconnect."""
    with patch("homeassistant.components.esphome.ReconnectLogic.start"):
        yield


@pytest.mark.parametrize(
    ("devices_payload", "expected_state", "expected_attributes"),
    [
        (
            [
                {
                    "name": "test",
                    "current_version": "2023.2.0-dev",
                    "configuration": "test.yaml",
                }
            ],
            "on",
            {
                "latest_version": "2023.2.0-dev",
                "installed_version": "1.0.0",
                "supported_features": UpdateEntityFeature.INSTALL,
            },
        ),
        (
            [
                {
                    "name": "test",
                    "current_version": "1.0.0",
                },
            ],
            "off",
            {
                "latest_version": "1.0.0",
                "installed_version": "1.0.0",
                "supported_features": 0,
            },
        ),
        (
            [],
            "unavailable",
            {"supported_features": 0},
        ),
    ],
)
async def test_update_entity(
    hass: HomeAssistant,
    mock_config_entry,
    mock_device_info,
    mock_dashboard,
    devices_payload,
    expected_state,
    expected_attributes,
) -> None:
    """Test ESPHome update entity."""
    mock_dashboard["configured"] = devices_payload
    await async_get_dashboard(hass).async_refresh()

    with patch(
        "homeassistant.components.esphome.update.DomainData.get_entry_data",
        return_value=Mock(available=True, device_info=mock_device_info),
    ):
        assert await hass.config_entries.async_forward_entry_setup(
            mock_config_entry, "update"
        )

    state = hass.states.get("update.none_firmware")
    assert state is not None
    assert state.state == expected_state
    for key, expected_value in expected_attributes.items():
        assert state.attributes.get(key) == expected_value

    if expected_state != "on":
        return

    with patch(
        "esphome_dashboard_api.ESPHomeDashboardAPI.compile", return_value=True
    ) as mock_compile, patch(
        "esphome_dashboard_api.ESPHomeDashboardAPI.upload", return_value=True
    ) as mock_upload:
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": "update.none_firmware"},
            blocking=True,
        )

    assert len(mock_compile.mock_calls) == 1
    assert mock_compile.mock_calls[0][1][0] == "test.yaml"

    assert len(mock_upload.mock_calls) == 1
    assert mock_upload.mock_calls[0][1][0] == "test.yaml"


async def test_update_static_info(
    hass: HomeAssistant,
    mock_config_entry,
    mock_device_info,
    mock_dashboard,
) -> None:
    """Test ESPHome update entity."""
    mock_dashboard["configured"] = [
        {
            "name": "test",
            "current_version": "1.2.3",
        },
    ]
    await async_get_dashboard(hass).async_refresh()

    signal_static_info_updated = f"esphome_{mock_config_entry.entry_id}_on_list"
    runtime_data = Mock(
        available=True,
        device_info=mock_device_info,
        signal_static_info_updated=signal_static_info_updated,
    )

    with patch(
        "homeassistant.components.esphome.update.DomainData.get_entry_data",
        return_value=runtime_data,
    ):
        assert await hass.config_entries.async_forward_entry_setup(
            mock_config_entry, "update"
        )

    state = hass.states.get("update.none_firmware")
    assert state is not None
    assert state.state == "on"

    runtime_data.device_info = dataclasses.replace(
        runtime_data.device_info, esphome_version="1.2.3"
    )
    async_dispatcher_send(hass, signal_static_info_updated, [])

    state = hass.states.get("update.none_firmware")
    assert state.state == "off"


async def test_update_device_state_for_availability(
    hass: HomeAssistant,
    mock_config_entry,
    mock_device_info,
    mock_dashboard,
) -> None:
    """Test ESPHome update entity changes availability with the device."""
    mock_dashboard["configured"] = [
        {
            "name": "test",
            "current_version": "1.2.3",
        },
    ]
    await async_get_dashboard(hass).async_refresh()

    signal_device_updated = f"esphome_{mock_config_entry.entry_id}_on_device_update"
    runtime_data = Mock(
        available=True,
        device_info=mock_device_info,
        signal_device_updated=signal_device_updated,
    )

    with patch(
        "homeassistant.components.esphome.update.DomainData.get_entry_data",
        return_value=runtime_data,
    ):
        assert await hass.config_entries.async_forward_entry_setup(
            mock_config_entry, "update"
        )

    state = hass.states.get("update.none_firmware")
    assert state is not None
    assert state.state == "on"

    runtime_data.available = False
    async_dispatcher_send(hass, signal_device_updated)

    state = hass.states.get("update.none_firmware")
    assert state.state == "unavailable"

    # Deep sleep devices should still be available
    runtime_data.device_info = dataclasses.replace(
        runtime_data.device_info, has_deep_sleep=True
    )

    async_dispatcher_send(hass, signal_device_updated)

    state = hass.states.get("update.none_firmware")
    assert state.state == "on"
