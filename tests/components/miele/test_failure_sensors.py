"""Tests for Miele failure detail sensors and failure coordinator behavior."""

from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from aiohttp import ClientResponseError
import pytest

from homeassistant.components.miele.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant

from . import get_data_callback, setup_integration

from tests.common import MockConfigEntry, async_load_json_object_fixture


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_fault_sensors_populated_when_device_signals_failure(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Failure endpoint is queried and fault sensors show API data when signalFailure is true."""
    devices = await async_load_json_object_fixture(hass, "4_devices.json", DOMAIN)
    devices["Dummy_Appliance_3"]["state"]["signalFailure"] = True
    mock_miele_client.get_devices.return_value = devices
    mock_miele_client.get_failure_details = AsyncMock(
        return_value={"error_number": 16, "message": "Detergent overload"}
    )

    with patch("homeassistant.components.miele.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_miele_client.get_failure_details.assert_awaited_once_with("Dummy_Appliance_3")
    assert hass.states.get("sensor.washing_machine_fault_code").state == "F16"
    assert (
        hass.states.get("sensor.washing_machine_fault_message").state
        == "Detergent overload"
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_fault_sensors_unknown_when_failure_api_errors(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """When failure details fail to load, fault sensors stay unknown."""
    devices = await async_load_json_object_fixture(hass, "4_devices.json", DOMAIN)
    devices["Dummy_Appliance_3"]["state"]["signalFailure"] = True
    mock_miele_client.get_devices.return_value = devices
    mock_miele_client.get_failure_details = AsyncMock(
        side_effect=ClientResponseError(Mock(), Mock(), status=503)
    )

    with patch("homeassistant.components.miele.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_miele_client.get_failure_details.assert_awaited()
    assert hass.states.get("sensor.washing_machine_fault_code").state == STATE_UNKNOWN
    assert (
        hass.states.get("sensor.washing_machine_fault_message").state == STATE_UNKNOWN
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_fault_data_cleared_when_signal_failure_cleared_via_push(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """After SSE push clears signalFailure, failure coordinator data is cleared."""
    devices = await async_load_json_object_fixture(hass, "4_devices.json", DOMAIN)
    devices["Dummy_Appliance_3"]["state"]["signalFailure"] = True
    mock_miele_client.get_devices.return_value = devices
    mock_miele_client.get_failure_details = AsyncMock(
        return_value={"error_number": 16, "message": "Detergent overload"}
    )

    with patch("homeassistant.components.miele.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.washing_machine_fault_code").state == "F16"

    cleared = deepcopy(devices)
    cleared["Dummy_Appliance_3"]["state"]["signalFailure"] = False
    data_callback = get_data_callback(mock_miele_client)
    await data_callback(cleared)
    await hass.async_block_till_done()

    mock_miele_client.get_failure_details.assert_awaited_once()
    assert hass.states.get("sensor.washing_machine_fault_code").state == STATE_UNKNOWN
    assert (
        hass.states.get("sensor.washing_machine_fault_message").state == STATE_UNKNOWN
    )
