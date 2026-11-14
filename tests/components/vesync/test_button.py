"""Tests for the button module."""

from datetime import timedelta
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_json_object_fixture,
    snapshot_platform,
)
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pyvesync.utils.errors import VeSyncAPIResponseError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, ButtonService
from homeassistant.components.vesync.const import DOMAIN
from homeassistant.const import CommonServiceArgument, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import REQUEST_REFRESH_DEFAULT_COOLDOWN

from .common import mock_devices_response, mock_firmware

ENTITY_RESET_FILTER = "button.air_purifier_200s_reset_filter"
RESET_FILTER = "pyvesync.devices.vesyncpurifier.VeSyncAirBypass.reset_filter"
UPDATE_ALL_DEVICES = "pyvesync.vesync.VeSync.update_all_devices"


async def test_button_state(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the resulting setup state is as expected for the platform."""

    mock_devices_response(aioclient_mock, "Air Purifier 200s")

    with patch("homeassistant.components.vesync.PLATFORMS", [Platform.BUTTON]):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_reset_filter(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test pressing the reset filter button resets the filter and refreshes."""

    mock_devices_response(aioclient_mock, "Air Purifier 200s")

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    with (
        patch(RESET_FILTER, return_value=True) as method_mock,
        patch(UPDATE_ALL_DEVICES) as update_mock,
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            ButtonService.PRESS,
            {CommonServiceArgument.ENTITY_ID: ENTITY_RESET_FILTER},
            blocking=True,
        )

        freezer.tick(timedelta(seconds=REQUEST_REFRESH_DEFAULT_COOLDOWN))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    method_mock.assert_called_once()
    update_mock.assert_called_once()


@pytest.mark.parametrize(
    "reset_filter",
    [
        {"return_value": False},
        {"side_effect": VeSyncAPIResponseError("API error")},
    ],
    ids=["returns_false", "raises"],
)
async def test_reset_filter_raises_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
    reset_filter: dict[str, Any],
) -> None:
    """Test a failed filter reset raises HomeAssistantError and skips the refresh."""

    mock_devices_response(aioclient_mock, "Air Purifier 200s")

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    with (
        patch(RESET_FILTER, **reset_filter) as method_mock,
        patch(UPDATE_ALL_DEVICES) as update_mock,
    ):
        with pytest.raises(
            HomeAssistantError, match="Invalid response from the VeSync API"
        ):
            await hass.services.async_call(
                BUTTON_DOMAIN,
                ButtonService.PRESS,
                {CommonServiceArgument.ENTITY_ID: ENTITY_RESET_FILTER},
                blocking=True,
            )

        freezer.tick(timedelta(seconds=REQUEST_REFRESH_DEFAULT_COOLDOWN))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    method_mock.assert_called_once()
    update_mock.assert_not_called()


FRYER = "CS158-AF Air Fryer Cooking"
FRYER_CLASS = "pyvesync.devices.vesynckitchen.VeSyncAirFryer158"


async def test_fryer_button_state(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the air fryer buttons are created."""

    mock_devices_response(aioclient_mock, FRYER)

    with patch("homeassistant.components.vesync.PLATFORMS", [Platform.BUTTON]):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "method"),
    [
        ("button.cs158_af_air_fryer_cooking_stop_cooking", "end"),
        ("button.cs158_af_air_fryer_cooking_pause_cooking", "stop"),
        ("button.cs158_af_air_fryer_cooking_resume_cooking", "resume"),
    ],
)
async def test_fryer_button_press(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
    entity_id: str,
    method: str,
) -> None:
    """Test pressing an air fryer button sends the command and refreshes."""

    mock_devices_response(aioclient_mock, FRYER)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    with (
        patch(f"{FRYER_CLASS}.{method}", return_value=True) as method_mock,
        patch(UPDATE_ALL_DEVICES) as update_mock,
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            ButtonService.PRESS,
            {CommonServiceArgument.ENTITY_ID: entity_id},
            blocking=True,
        )

        freezer.tick(timedelta(seconds=REQUEST_REFRESH_DEFAULT_COOLDOWN))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    method_mock.assert_called_once_with(1)
    update_mock.assert_called_once()


async def test_fryer_button_press_fails(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a rejected air fryer command raises HomeAssistantError."""

    mock_devices_response(aioclient_mock, FRYER)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    with (
        patch(f"{FRYER_CLASS}.end", return_value=False),
        pytest.raises(HomeAssistantError, match="Invalid response from the VeSync API"),
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            ButtonService.PRESS,
            {
                CommonServiceArgument.ENTITY_ID: (
                    "button.cs158_af_air_fryer_cooking_stop_cooking"
                )
            },
            blocking=True,
        )


DUAL_FRYER_CLASS = "pyvesync.devices.vesynckitchen.VeSyncDualAirFryer"


def mock_dual_fryer(aioclient_mock: AiohttpClientMocker, device_type: str) -> None:
    """Mock a dual basket air fryer of the given type with both baskets cooking."""
    aioclient_mock.post(
        "https://smartapi.vesync.com/cloud/v1/deviceManaged/devices",
        json={
            "traceId": "1234",
            "code": 0,
            "msg": None,
            "module": None,
            "stacktrace": None,
            "result": {
                "total": 1,
                "pageSize": 1,
                "pageNo": 1,
                "list": [
                    {
                        "deviceRegion": "EU",
                        "isOwner": True,
                        "deviceName": "Dual Fryer",
                        "deviceImg": "",
                        "cid": "DualFryer",
                        "deviceStatus": "on",
                        "connectionStatus": "online",
                        "connectionType": "wifi",
                        "deviceType": device_type,
                        "type": "SKA",
                        "uuid": "##_REDACTED_##",
                        "configModule": f"VS_WFON_{device_type}_EU",
                        "currentFirmVersion": None,
                        "subDeviceNo": None,
                        "subDeviceType": None,
                    }
                ],
            },
        },
    )
    aioclient_mock.post(
        "https://smartapi.vesync.com/cloud/v2/deviceManaged/bypassV2",
        json=load_json_object_fixture("air-fryer-CAF-DC111S-AEU-detail.json", DOMAIN),
    )
    mock_firmware(aioclient_mock)


@pytest.mark.parametrize(
    "device_type",
    [
        "CAF-DC111S-AEU",  # dual basket, can pause
        "CAF-TF101S",  # dual basket, cannot pause
    ],
)
async def test_dual_fryer_button_state(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    device_type: str,
) -> None:
    """Test dual basket fryers get the buttons once per basket."""

    mock_dual_fryer(aioclient_mock, device_type)

    with patch("homeassistant.components.vesync.PLATFORMS", [Platform.BUTTON]):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "method", "chamber"),
    [
        ("button.dual_fryer_basket_1_stop_cooking", "end", 1),
        ("button.dual_fryer_basket_2_stop_cooking", "end", 2),
        ("button.dual_fryer_basket_1_pause_cooking", "stop", 1),
        ("button.dual_fryer_basket_2_pause_cooking", "stop", 2),
        ("button.dual_fryer_basket_1_resume_cooking", "resume", 1),
        ("button.dual_fryer_basket_2_resume_cooking", "resume", 2),
    ],
)
async def test_dual_fryer_button_press(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    entity_id: str,
    method: str,
    chamber: int,
) -> None:
    """Test each basket button sends the command for its own basket."""

    mock_dual_fryer(aioclient_mock, "CAF-DC111S-AEU")

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    with (
        patch(f"{DUAL_FRYER_CLASS}.{method}", return_value=True) as method_mock,
        patch(UPDATE_ALL_DEVICES),
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            ButtonService.PRESS,
            {CommonServiceArgument.ENTITY_ID: entity_id},
            blocking=True,
        )

    method_mock.assert_called_once_with(chamber)
