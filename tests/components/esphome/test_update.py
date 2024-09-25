"""Test ESPHome update entities."""

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import Mock, patch

from aioesphomeapi import (
    APIClient,
    EntityInfo,
    EntityState,
    UpdateCommand,
    UpdateInfo,
    UpdateState,
    UserService,
)
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
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import MockESPHomeDevice


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
        (
            [],
            STATE_UNKNOWN,  # dashboard is available but device is unknown
            {"supported_features": 0},
        ),
    ],
)
async def test_update_entity(
    hass: HomeAssistant,
    stub_reconnect,
    mock_config_entry,
    mock_device_info,
    mock_dashboard: dict[str, Any],
    devices_payload,
    expected_state,
    expected_attributes,
) -> None:
    """Test ESPHome update entity."""
    mock_dashboard["configured"] = devices_payload
    await async_get_dashboard(hass).async_refresh()

    with patch(
        "homeassistant.components.esphome.update.DomainData.get_entry_data",
        return_value=Mock(available=True, device_info=mock_device_info, info={}),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("update.none_firmware")
    assert state is not None
    assert state.state == expected_state
    for key, expected_value in expected_attributes.items():
        assert state.attributes.get(key) == expected_value

    if expected_state != "on":
        return

    # Compile failed, don't try to upload
    with (
        patch(
            "esphome_dashboard_api.ESPHomeDashboardAPI.compile", return_value=False
        ) as mock_compile,
        patch(
            "esphome_dashboard_api.ESPHomeDashboardAPI.upload", return_value=True
        ) as mock_upload,
        pytest.raises(
            HomeAssistantError,
            match="compiling",
        ),
    ):
        await hass.services.async_call(
            "update",
            "install",
            {"entity_id": "update.none_firmware"},
            blocking=True,
        )

    assert len(mock_compile.mock_calls) == 1
    assert mock_compile.mock_calls[0][1][0] == "test.yaml"

    assert len(mock_upload.mock_calls) == 0

    # Compile success, upload fails
    with (
        patch(
            "esphome_dashboard_api.ESPHomeDashboardAPI.compile", return_value=True
        ) as mock_compile,
        patch(
            "esphome_dashboard_api.ESPHomeDashboardAPI.upload", return_value=False
        ) as mock_upload,
        pytest.raises(
            HomeAssistantError,
            match="OTA",
        ),
    ):
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

    # Everything works
    with (
        patch(
            "esphome_dashboard_api.ESPHomeDashboardAPI.compile", return_value=True
        ) as mock_compile,
        patch(
            "esphome_dashboard_api.ESPHomeDashboardAPI.upload", return_value=True
        ) as mock_upload,
    ):
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
    mock_client: APIClient,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
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

    mock_device: MockESPHomeDevice = await mock_esphome_device(
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
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
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
    stub_reconnect,
    mock_config_entry,
    mock_device_info,
    mock_dashboard: dict[str, Any],
) -> None:
    """Test ESPHome update entity when dashboard is not available at startup."""
    with (
        patch(
            "homeassistant.components.esphome.update.DomainData.get_entry_data",
            return_value=Mock(available=True, device_info=mock_device_info, info={}),
        ),
        patch(
            "esphome_dashboard_api.ESPHomeDashboardAPI.get_devices",
            side_effect=TimeoutError,
        ),
    ):
        await async_get_dashboard(hass).async_refresh()
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # We have a dashboard but it is not available
    state = hass.states.get("update.none_firmware")
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

    state = hass.states.get("update.none_firmware")
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
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
    mock_dashboard: dict[str, Any],
) -> None:
    """Test ESPHome update entity when dashboard is discovered after startup and the first update fails."""
    with patch(
        "esphome_dashboard_api.ESPHomeDashboardAPI.get_devices",
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
    hass: HomeAssistant, stub_reconnect, mock_config_entry, mock_device_info
) -> None:
    """Test ESPHome update entity does not get created if there is no dashboard."""
    with patch(
        "homeassistant.components.esphome.update.DomainData.get_entry_data",
        return_value=Mock(available=True, device_info=mock_device_info, info={}),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("update.none_firmware")
    assert state is None


async def test_update_becomes_available_at_runtime(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
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
    assert state is not None
    features = state.attributes[ATTR_SUPPORTED_FEATURES]
    # There are no devices on the dashboard so no
    # way to tell the version so install is disabled
    assert features is UpdateEntityFeature(0)

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


async def test_generic_device_update_entity(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_generic_device_entry,
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
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
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
    mock_device: MockESPHomeDevice = await mock_esphome_device(
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
    assert state.attributes["in_progress"] == 50

    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: "update.test_myupdate"},
        blocking=True,
    )

    mock_client.update_command.assert_called_with(key=1, command=UpdateCommand.CHECK)
