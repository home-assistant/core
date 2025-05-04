"""Test ESPHome update entities."""

import asyncio
from typing import Any
from unittest.mock import patch

from aioesphomeapi import APIClient, UpdateCommand, UpdateInfo, UpdateState
import pytest

from homeassistant.components.esphome.dashboard import async_get_dashboard
from homeassistant.components.homeassistant import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.update import (
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
    UpdateEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import MockESPHomeDeviceType, MockGenericDeviceEntryType


@pytest.fixture(autouse=True)
def enable_entity(entity_registry_enabled_by_default: None) -> None:
    """Enable update entity."""


@pytest.fixture
def stub_reconnect():
    """Stub reconnect."""
    with patch("homeassistant.components.esphome.manager.ReconnectLogic.start"):
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
            STATE_ON,
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
            STATE_OFF,
            {
                "latest_version": "1.0.0",
                "installed_version": "1.0.0",
                "supported_features": 0,
            },
        ),
    ],
)
async def test_update_entity(
    hass: HomeAssistant,
    mock_dashboard: dict[str, Any],
    devices_payload: list[dict[str, Any]],
    expected_state: str,
    expected_attributes: dict[str, Any],
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test ESPHome update entity."""
    mock_dashboard["configured"] = devices_payload
    await async_get_dashboard(hass).async_refresh()

    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=[],
        user_service=[],
        states=[],
    )

    state = hass.states.get("update.test_firmware")
    assert state is not None
    assert state.state == expected_state
    for key, expected_value in expected_attributes.items():
        assert state.attributes.get(key) == expected_value

    if expected_state != "on":
        return

    # Compile failed, don't try to upload
    with (
        patch(
            "homeassistant.components.esphome.coordinator.ESPHomeDashboardAPI.compile",
            return_value=False,
        ) as mock_compile,
        patch(
            "homeassistant.components.esphome.coordinator.ESPHomeDashboardAPI.upload",
            return_value=True,
        ) as mock_upload,
        pytest.raises(
            HomeAssistantError,
            match="compiling",
        ),
    ):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: "update.test_firmware"},
            blocking=True,
        )

    assert len(mock_compile.mock_calls) == 1
    assert mock_compile.mock_calls[0][1][0] == "test.yaml"

    assert len(mock_upload.mock_calls) == 0

    # Compile success, upload fails
    with (
        patch(
            "homeassistant.components.esphome.coordinator.ESPHomeDashboardAPI.compile",
            return_value=True,
        ) as mock_compile,
        patch(
            "homeassistant.components.esphome.coordinator.ESPHomeDashboardAPI.upload",
            return_value=False,
        ) as mock_upload,
        pytest.raises(
            HomeAssistantError,
            match="OTA",
        ),
    ):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: "update.test_firmware"},
            blocking=True,
        )

    assert len(mock_compile.mock_calls) == 1
    assert mock_compile.mock_calls[0][1][0] == "test.yaml"

    assert len(mock_upload.mock_calls) == 1
    assert mock_upload.mock_calls[0][1][0] == "test.yaml"

    # Everything works
    with (
        patch(
            "homeassistant.components.esphome.coordinator.ESPHomeDashboardAPI.compile",
            return_value=True,
        ) as mock_compile,
        patch(
            "homeassistant.components.esphome.coordinator.ESPHomeDashboardAPI.upload",
            return_value=True,
        ) as mock_upload,
    ):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: "update.test_firmware"},
            blocking=True,
        )

    assert len(mock_compile.mock_calls) == 1
    assert mock_compile.mock_calls[0][1][0] == "test.yaml"

    assert len(mock_upload.mock_calls) == 1
    assert mock_upload.mock_calls[0][1][0] == "test.yaml"


async def test_update_static_info(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    mock_dashboard: dict[str, Any],
) -> None:
    """Test ESPHome update entity."""
    mock_dashboard["configured"] = [
        {
            "name": "test",
            "current_version": "1.2.3",
        },
    ]
    await async_get_dashboard(hass).async_refresh()

    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=[],
        user_service=[],
        states=[],
    )

    state = hass.states.get("update.test_firmware")
    assert state is not None
    assert state.state == STATE_ON

    object.__setattr__(mock_device.device_info, "esphome_version", "1.2.3")
    await mock_device.mock_disconnect(True)
    await mock_device.mock_connect()

    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("update.test_firmware")
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    ("expected_disconnect", "expected_state", "has_deep_sleep"),
    [
        (True, STATE_ON, False),
        (False, STATE_UNAVAILABLE, False),
        (True, STATE_ON, True),
        (False, STATE_ON, True),
    ],
)
async def test_update_device_state_for_availability(
    hass: HomeAssistant,
    expected_disconnect: bool,
    expected_state: str,
    has_deep_sleep: bool,
    mock_dashboard: dict[str, Any],
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test ESPHome update entity changes availability with the device."""
    mock_dashboard["configured"] = [
        {
            "name": "test",
            "current_version": "1.2.3",
        },
    ]
    await async_get_dashboard(hass).async_refresh()
    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=[],
        user_service=[],
        states=[],
        device_info={"has_deep_sleep": has_deep_sleep},
    )

    state = hass.states.get("update.test_firmware")
    assert state is not None
    assert state.state == STATE_ON
    await mock_device.mock_disconnect(expected_disconnect)
    state = hass.states.get("update.test_firmware")
    assert state.state == expected_state


async def test_update_entity_dashboard_not_available_startup(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    mock_dashboard: dict[str, Any],
) -> None:
    """Test ESPHome update entity when dashboard is not available at startup."""
    with (
        patch(
            "homeassistant.components.esphome.coordinator.ESPHomeDashboardAPI.get_devices",
            side_effect=TimeoutError,
        ),
    ):
        await async_get_dashboard(hass).async_refresh()
        await mock_esphome_device(
            mock_client=mock_client,
            entity_info=[],
            user_service=[],
            states=[],
        )

    # We have a dashboard but it is not available
    state = hass.states.get("update.test_firmware")
    assert state is None

    mock_dashboard["configured"] = [
        {
            "name": "test",
            "current_version": "2023.2.0-dev",
            "configuration": "test.yaml",
        }
    ]
    await async_get_dashboard(hass).async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("update.test_firmware")
    assert state.state == STATE_ON
    expected_attributes = {
        "latest_version": "2023.2.0-dev",
        "installed_version": "1.0.0",
        "supported_features": UpdateEntityFeature.INSTALL,
    }
    for key, expected_value in expected_attributes.items():
        assert state.attributes.get(key) == expected_value


async def test_update_entity_dashboard_discovered_after_startup_but_update_failed(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    mock_dashboard: dict[str, Any],
) -> None:
    """Test ESPHome update entity when dashboard is discovered after startup and the first update fails."""
    with patch(
        "homeassistant.components.esphome.coordinator.ESPHomeDashboardAPI.get_devices",
        side_effect=TimeoutError,
    ):
        await async_get_dashboard(hass).async_refresh()
        await hass.async_block_till_done()
        mock_device = await mock_esphome_device(
            mock_client=mock_client,
            entity_info=[],
            user_service=[],
            states=[],
        )
        await hass.async_block_till_done()
    state = hass.states.get("update.test_firmware")
    assert state is None

    await mock_device.mock_disconnect(False)

    mock_dashboard["configured"] = [
        {
            "name": "test",
            "current_version": "2023.2.0-dev",
            "configuration": "test.yaml",
        }
    ]
    # Device goes unavailable, and dashboard becomes available
    await async_get_dashboard(hass).async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("update.test_firmware")
    assert state is None

    # Finally both are available
    await mock_device.mock_connect()
    await async_get_dashboard(hass).async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get("update.test_firmware")
    assert state is not None


async def test_update_entity_not_present_without_dashboard(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test ESPHome update entity does not get created if there is no dashboard."""
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=[],
        user_service=[],
        states=[],
    )

    state = hass.states.get("update.test_firmware")
    assert state is None


async def test_update_becomes_available_at_runtime(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    mock_dashboard: dict[str, Any],
) -> None:
    """Test ESPHome update entity when the dashboard has no device at startup but gets them later."""
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=[],
        user_service=[],
        states=[],
    )
    await hass.async_block_till_done()
    state = hass.states.get("update.test_firmware")
    assert state is None

    # A device gets added to the dashboard
    mock_dashboard["configured"] = [
        {
            "name": "test",
            "current_version": "2023.2.0-dev",
            "configuration": "test.yaml",
        }
    ]

    await async_get_dashboard(hass).async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("update.test_firmware")
    assert state is not None
    # We now know the version so install is enabled
    features = state.attributes[ATTR_SUPPORTED_FEATURES]
    assert features is UpdateEntityFeature.INSTALL


async def test_update_entity_not_present_with_dashboard_but_unknown_device(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    mock_dashboard: dict[str, Any],
) -> None:
    """Test ESPHome update entity does not get created if the device is unknown to the dashboard."""
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=[],
        user_service=[],
        states=[],
    )

    mock_dashboard["configured"] = [
        {
            "name": "other-test",
            "current_version": "2023.2.0-dev",
            "configuration": "other-test.yaml",
        }
    ]

    state = hass.states.get("update.test_firmware")
    assert state is None

    await async_get_dashboard(hass).async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("update.none_firmware")
    assert state is None


async def test_generic_device_update_entity(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry: MockGenericDeviceEntryType,
) -> None:
    """Test a generic device update entity."""
    entity_info = [
        UpdateInfo(
            object_id="myupdate",
            key=1,
            name="my update",
            unique_id="my_update",
        )
    ]
    states = [
        UpdateState(
            key=1,
            current_version="2024.6.0",
            latest_version="2024.6.0",
            title="ESPHome Project",
            release_summary="This is a release summary",
            release_url="https://esphome.io/changelog",
        )
    ]
    user_service = []
    await mock_generic_device_entry(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("update.test_myupdate")
    assert state is not None
    assert state.state == STATE_OFF


async def test_generic_device_update_entity_has_update(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test a generic device update entity with an update."""
    entity_info = [
        UpdateInfo(
            object_id="myupdate",
            key=1,
            name="my update",
            unique_id="my_update",
        )
    ]
    states = [
        UpdateState(
            key=1,
            current_version="2024.6.0",
            latest_version="2024.6.1",
            title="ESPHome Project",
            release_summary="This is a release summary",
            release_url="https://esphome.io/changelog",
        )
    ]
    user_service = []
    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("update.test_myupdate")
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.test_myupdate"},
        blocking=True,
    )

    mock_device.set_state(
        UpdateState(
            key=1,
            in_progress=True,
            has_progress=True,
            progress=50,
            current_version="2024.6.0",
            latest_version="2024.6.1",
            title="ESPHome Project",
            release_summary="This is a release summary",
            release_url="https://esphome.io/changelog",
        )
    )

    state = hass.states.get("update.test_myupdate")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes["in_progress"] is True
    assert state.attributes["update_percentage"] == 50

    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: "update.test_myupdate"},
        blocking=True,
    )

    mock_client.update_command.assert_called_with(key=1, command=UpdateCommand.CHECK)


async def test_attempt_to_update_twice(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    mock_dashboard: dict[str, Any],
) -> None:
    """Test attempting to update twice."""
    mock_dashboard["configured"] = [
        {
            "name": "test",
            "current_version": "2023.2.0-dev",
            "configuration": "test.yaml",
        }
    ]
    await async_get_dashboard(hass).async_refresh()
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=[],
        user_service=[],
        states=[],
    )
    await hass.async_block_till_done()
    state = hass.states.get("update.test_firmware")
    assert state is not None

    async def delayed_compile(*args: Any, **kwargs: Any) -> None:
        """Delay the update."""
        await asyncio.sleep(0)
        return True

    # Compile success, upload fails
    with (
        patch(
            "homeassistant.components.esphome.coordinator.ESPHomeDashboardAPI.compile",
            delayed_compile,
        ),
        patch(
            "homeassistant.components.esphome.coordinator.ESPHomeDashboardAPI.upload",
            return_value=False,
        ),
    ):
        update_task = hass.async_create_task(
            hass.services.async_call(
                UPDATE_DOMAIN,
                SERVICE_INSTALL,
                {ATTR_ENTITY_ID: "update.test_firmware"},
                blocking=True,
            )
        )

        with pytest.raises(HomeAssistantError, match="update is already in progress"):
            await hass.services.async_call(
                UPDATE_DOMAIN,
                SERVICE_INSTALL,
                {ATTR_ENTITY_ID: "update.test_firmware"},
                blocking=True,
            )

        with pytest.raises(HomeAssistantError, match="OTA"):
            await update_task


async def test_update_deep_sleep_already_online(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    mock_dashboard: dict[str, Any],
) -> None:
    """Test attempting to update twice."""
    mock_dashboard["configured"] = [
        {
            "name": "test",
            "current_version": "2023.2.0-dev",
            "configuration": "test.yaml",
        }
    ]
    await async_get_dashboard(hass).async_refresh()
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=[],
        user_service=[],
        states=[],
        device_info={"has_deep_sleep": True},
    )
    await hass.async_block_till_done()
    state = hass.states.get("update.test_firmware")
    assert state is not None

    # Compile success, upload fails
    with (
        patch(
            "homeassistant.components.esphome.coordinator.ESPHomeDashboardAPI.compile",
            return_value=True,
        ),
        patch(
            "homeassistant.components.esphome.coordinator.ESPHomeDashboardAPI.upload",
            return_value=True,
        ),
    ):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: "update.test_firmware"},
            blocking=True,
        )


async def test_update_deep_sleep_offline(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    mock_dashboard: dict[str, Any],
) -> None:
    """Test device comes online while updating."""
    mock_dashboard["configured"] = [
        {
            "name": "test",
            "current_version": "2023.2.0-dev",
            "configuration": "test.yaml",
        }
    ]
    await async_get_dashboard(hass).async_refresh()
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=[],
        user_service=[],
        states=[],
        device_info={"has_deep_sleep": True},
    )
    await hass.async_block_till_done()
    state = hass.states.get("update.test_firmware")
    assert state is not None
    await device.mock_disconnect(True)

    # Compile success, upload fails
    with (
        patch(
            "homeassistant.components.esphome.coordinator.ESPHomeDashboardAPI.compile",
            return_value=True,
        ),
        patch(
            "homeassistant.components.esphome.coordinator.ESPHomeDashboardAPI.upload",
            return_value=True,
        ),
    ):
        update_task = hass.async_create_task(
            hass.services.async_call(
                UPDATE_DOMAIN,
                SERVICE_INSTALL,
                {ATTR_ENTITY_ID: "update.test_firmware"},
                blocking=True,
            )
        )
        await asyncio.sleep(0)
        assert not update_task.done()
        await device.mock_connect()
        await hass.async_block_till_done()


async def test_update_deep_sleep_offline_sleep_during_ota(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    mock_dashboard: dict[str, Any],
) -> None:
    """Test device comes online too late during update."""
    mock_dashboard["configured"] = [
        {
            "name": "test",
            "current_version": "2023.2.0-dev",
            "configuration": "test.yaml",
        }
    ]
    await async_get_dashboard(hass).async_refresh()
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=[],
        user_service=[],
        states=[],
        device_info={"has_deep_sleep": True},
    )
    await hass.async_block_till_done()
    state = hass.states.get("update.test_firmware")
    assert state is not None
    await device.mock_disconnect(True)

    upload_attempt = 0
    upload_attempt_2_future = hass.loop.create_future()

    async def upload_takes_a_while(*args: Any, **kwargs: Any) -> None:
        """Delay the update."""
        nonlocal upload_attempt
        upload_attempt += 1
        if upload_attempt == 1:
            # First attempt fails
            return False
        upload_attempt_2_future.set_result(None)
        return True

    # Compile success, upload fails
    with (
        patch(
            "homeassistant.components.esphome.coordinator.ESPHomeDashboardAPI.compile",
            return_value=True,
        ),
        patch(
            "homeassistant.components.esphome.coordinator.ESPHomeDashboardAPI.upload",
            upload_takes_a_while,
        ),
    ):
        update_task = hass.async_create_task(
            hass.services.async_call(
                UPDATE_DOMAIN,
                SERVICE_INSTALL,
                {ATTR_ENTITY_ID: "update.test_firmware"},
                blocking=True,
            )
        )
        await asyncio.sleep(0)
        assert not update_task.done()
        await device.mock_connect()
        # Mock device being at the end of its sleep cycle
        # and going to sleep right as the upload starts
        await device.mock_disconnect(True)
        assert not upload_attempt_2_future.done()
        # Now the device wakes up and the upload is attempted
        await device.mock_connect()
        await upload_attempt_2_future
        await hass.async_block_till_done()
