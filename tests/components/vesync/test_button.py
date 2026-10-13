"""Tests for the button module."""

from unittest.mock import patch

import pytest
from pyvesync.utils.errors import ResponseInfo
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import ALL_DEVICE_NAMES, mock_devices_response

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

ENTITY_RESET_FILTER = "button.air_purifier_200s_reset_filter"
RESET_FILTER = "pyvesync.devices.vesyncpurifier.VeSyncAirBypass.reset_filter"


@pytest.mark.parametrize("device_name", ALL_DEVICE_NAMES)
async def test_button_state(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    device_name: str,
) -> None:
    """Test the resulting setup state is as expected for the platform."""

    mock_devices_response(aioclient_mock, device_name)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    devices = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    assert devices == snapshot(name="devices")

    entities = [
        entity
        for entity in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entity.domain == BUTTON_DOMAIN
    ]
    assert entities == snapshot(name="entities")

    for entity in entities:
        assert hass.states.get(entity.entity_id) == snapshot(name=entity.entity_id)


async def test_reset_filter(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test pressing the reset filter button resets the filter and refreshes."""

    mock_devices_response(aioclient_mock, "Air Purifier 200s")

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    with (
        patch(RESET_FILTER, return_value=True) as method_mock,
        patch(
            "homeassistant.components.vesync.coordinator.VeSyncDataCoordinator.async_request_refresh"
        ) as refresh_mock,
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: ENTITY_RESET_FILTER},
            blocking=True,
        )

    method_mock.assert_called_once()
    refresh_mock.assert_called_once()


@pytest.mark.parametrize(
    ("last_response", "message"),
    [
        (
            ResponseInfo(name="api_error", error_type="api_error", message="API error"),
            "API error",
        ),
        (None, "Unknown error pressing button, no response."),
    ],
)
async def test_reset_filter_raises_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    last_response: ResponseInfo | None,
    message: str,
) -> None:
    """Test a failed filter reset raises HomeAssistantError and skips the refresh."""

    mock_devices_response(aioclient_mock, "Air Purifier 200s")

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    for device in config_entry.runtime_data.manager.devices:
        device.last_response = last_response

    with (
        patch(RESET_FILTER, return_value=False) as method_mock,
        patch(
            "homeassistant.components.vesync.coordinator.VeSyncDataCoordinator.async_request_refresh"
        ) as refresh_mock,
        pytest.raises(HomeAssistantError, match=message),
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: ENTITY_RESET_FILTER},
            blocking=True,
        )

    method_mock.assert_called_once()
    refresh_mock.assert_not_called()
