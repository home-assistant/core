"""The tests for the Update component."""
from collections.abc import Awaitable, Callable
from unittest.mock import MagicMock, patch

from aiohttp import ClientWebSocketResponse
import pytest

from homeassistant.components.update import (
    ATTR_BACKUP,
    ATTR_VERSION,
    DOMAIN,
    SERVICE_INSTALL,
    SERVICE_SKIP,
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
)
from homeassistant.components.update.const import (
    ATTR_AUTO_UPDATE,
    ATTR_IN_PROGRESS,
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    ATTR_RELEASE_SUMMARY,
    ATTR_RELEASE_URL,
    ATTR_SKIPPED_VERSION,
    ATTR_TITLE,
    UpdateEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_PLATFORM,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.setup import async_setup_component

from tests.common import MockEntityPlatform, mock_restore_cache


class MockUpdateEntity(UpdateEntity):
    """Mock UpdateEntity to use in tests."""


async def test_update(hass: HomeAssistant) -> None:
    """Test getting data from the mocked update entity."""
    update = MockUpdateEntity()
    update.hass = hass

    update._attr_installed_version = "1.0.0"
    update._attr_latest_version = "1.0.1"
    update._attr_release_summary = "Summary"
    update._attr_release_url = "https://example.com"
    update._attr_title = "Title"

    assert update.entity_category is EntityCategory.DIAGNOSTIC
    assert update.entity_picture is None
    assert update.installed_version == "1.0.0"
    assert update.latest_version == "1.0.1"
    assert update.release_summary == "Summary"
    assert update.release_url == "https://example.com"
    assert update.title == "Title"
    assert update.in_progress is False
    assert update.state == STATE_ON
    assert update.state_attributes == {
        ATTR_AUTO_UPDATE: False,
        ATTR_INSTALLED_VERSION: "1.0.0",
        ATTR_IN_PROGRESS: False,
        ATTR_LATEST_VERSION: "1.0.1",
        ATTR_RELEASE_SUMMARY: "Summary",
        ATTR_RELEASE_URL: "https://example.com",
        ATTR_SKIPPED_VERSION: None,
        ATTR_TITLE: "Title",
    }

    # Test with platform
    update.platform = MockEntityPlatform(hass)
    assert (
        update.entity_picture
        == "https://brands.home-assistant.io/_/test_platform/icon.png"
    )

    # Test no update available
    update._attr_installed_version = "1.0.0"
    update._attr_latest_version = "1.0.0"
    assert update.state is STATE_OFF

    # Test state becomes unknown if installed version is unknown
    update._attr_installed_version = None
    update._attr_latest_version = "1.0.0"
    assert update.state is None

    # Test state becomes unknown if latest version is unknown
    update._attr_installed_version = "1.0.0"
    update._attr_latest_version = None
    assert update.state is None

    # Test no update if new version is not an update
    update._attr_installed_version = "1.0.0"
    update._attr_latest_version = "0.9.0"
    assert update.state is STATE_OFF

    # Test update if new version is not considered a valid version
    update._attr_installed_version = "1.0.0"
    update._attr_latest_version = "awesome_update"
    assert update.state is STATE_ON

    # Test entity category becomes config when its possible to install
    update._attr_supported_features = UpdateEntityFeature.INSTALL
    assert update.entity_category is EntityCategory.CONFIG

    # UpdateEntityDescription was set
    update._attr_supported_features = 0
    update.entity_description = UpdateEntityDescription(key="F5 - Its very refreshing")
    assert update.device_class is None
    assert update.entity_category is EntityCategory.CONFIG
    update.entity_description = UpdateEntityDescription(
        key="F5 - Its very refreshing",
        device_class=UpdateDeviceClass.FIRMWARE,
        entity_category=None,
    )
    assert update.device_class is UpdateDeviceClass.FIRMWARE
    assert update.entity_category is None

    # Device class via attribute (override entity description)
    update._attr_device_class = None
    assert update.device_class is None
    update._attr_device_class = UpdateDeviceClass.FIRMWARE
    assert update.device_class is UpdateDeviceClass.FIRMWARE

    # Entity Attribute via attribute (override entity description)
    update._attr_entity_category = None
    assert update.entity_category is None
    update._attr_entity_category = EntityCategory.DIAGNOSTIC
    assert update.entity_category is EntityCategory.DIAGNOSTIC

    with pytest.raises(NotImplementedError):
        await update.async_install(version=None, backup=True)

    with pytest.raises(NotImplementedError):
        update.install(version=None, backup=False)

    update.install = MagicMock()
    await update.async_install(version="1.0.1", backup=True)

    assert update.install.called
    assert update.install.call_args[0][0] == "1.0.1"
    assert update.install.call_args[0][1] is True


async def test_entity_with_no_install(
    hass: HomeAssistant,
    enable_custom_integrations: None,
) -> None:
    """Test entity with no updates."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    # Update is available
    state = hass.states.get("update.update_no_install")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.0.0"
    assert state.attributes[ATTR_LATEST_VERSION] == "1.0.1"

    # Should not be able to install as the entity doesn't support that
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: "update.update_no_install"},
            blocking=True,
        )

    # Nothing changed
    state = hass.states.get("update.update_no_install")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.0.0"
    assert state.attributes[ATTR_LATEST_VERSION] == "1.0.1"
    assert state.attributes[ATTR_SKIPPED_VERSION] is None

    # We can mark the update as skipped
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SKIP,
        {ATTR_ENTITY_ID: "update.update_no_install"},
        blocking=True,
    )

    state = hass.states.get("update.update_no_install")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.0.0"
    assert state.attributes[ATTR_LATEST_VERSION] == "1.0.1"
    assert state.attributes[ATTR_SKIPPED_VERSION] == "1.0.1"

    # We can clear the skipped marker again
    await hass.services.async_call(
        DOMAIN,
        "clear_skipped",
        {ATTR_ENTITY_ID: "update.update_no_install"},
        blocking=True,
    )

    state = hass.states.get("update.update_no_install")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.0.0"
    assert state.attributes[ATTR_LATEST_VERSION] == "1.0.1"
    assert state.attributes[ATTR_SKIPPED_VERSION] is None


async def test_entity_with_no_updates(
    hass: HomeAssistant,
    enable_custom_integrations: None,
) -> None:
    """Test entity with no updates."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    # No update available
    state = hass.states.get("update.no_update")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.0.0"
    assert state.attributes[ATTR_LATEST_VERSION] == "1.0.0"

    # Should not be able to skip when there is no update available
    with pytest.raises(HomeAssistantError, match="No update available to skip for"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SKIP,
            {ATTR_ENTITY_ID: "update.no_update"},
            blocking=True,
        )

    # Should not be able to install an update when there is no update available
    with pytest.raises(HomeAssistantError, match="No update available for"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: "update.no_update"},
            blocking=True,
        )

    # Updating to a specific version is not supported by this entity
    with pytest.raises(
        HomeAssistantError,
        match="Installing a specific version is not supported for",
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_INSTALL,
            {ATTR_VERSION: "0.9.0", ATTR_ENTITY_ID: "update.no_update"},
            blocking=True,
        )


async def test_entity_with_auto_update(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update entity that has auto update feature."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    state = hass.states.get("update.update_with_auto_update")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.0.0"
    assert state.attributes[ATTR_LATEST_VERSION] == "1.0.1"
    assert state.attributes[ATTR_SKIPPED_VERSION] is None

    # Should be able to manually install an update even if it can auto update
    await hass.services.async_call(
        DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.update_with_auto_update"},
        blocking=True,
    )

    # Should not be able to skip the update
    with pytest.raises(
        HomeAssistantError,
        match="Skipping update is not supported for Update with auto update",
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SKIP,
            {ATTR_ENTITY_ID: "update.update_with_auto_update"},
            blocking=True,
        )

    # Should not be able to clear a skipped the update
    with pytest.raises(
        HomeAssistantError,
        match="Clearing skipped update is not supported for Update with auto update",
    ):
        await hass.services.async_call(
            DOMAIN,
            "clear_skipped",
            {ATTR_ENTITY_ID: "update.update_with_auto_update"},
            blocking=True,
        )


async def test_entity_with_updates_available(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test basic update entity with updates available."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    # Entity has an update available
    state = hass.states.get("update.update_available")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.0.0"
    assert state.attributes[ATTR_LATEST_VERSION] == "1.0.1"
    assert state.attributes[ATTR_SKIPPED_VERSION] is None

    # Skip skip the update
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SKIP,
        {ATTR_ENTITY_ID: "update.update_available"},
        blocking=True,
    )

    # The state should have changed to off, skipped version should be set
    state = hass.states.get("update.update_available")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.0.0"
    assert state.attributes[ATTR_LATEST_VERSION] == "1.0.1"
    assert state.attributes[ATTR_SKIPPED_VERSION] == "1.0.1"

    # Even though skipped, we can still update if we want to
    await hass.services.async_call(
        DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.update_available"},
        blocking=True,
    )

    # The state should have changed to off, skipped version should be set
    state = hass.states.get("update.update_available")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.0.1"
    assert state.attributes[ATTR_LATEST_VERSION] == "1.0.1"
    assert state.attributes[ATTR_SKIPPED_VERSION] is None
    assert "Installed latest update" in caplog.text


async def test_entity_with_unknown_version(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update entity that has an unknown version."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    state = hass.states.get("update.update_unknown")
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.0.0"
    assert state.attributes[ATTR_LATEST_VERSION] is None
    assert state.attributes[ATTR_SKIPPED_VERSION] is None

    # Should not be able to install an update when there is no update available
    with pytest.raises(HomeAssistantError, match="No update available for"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: "update.update_unknown"},
            blocking=True,
        )

    # Should not be to skip the update
    with pytest.raises(HomeAssistantError, match="Cannot skip an unknown version for"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SKIP,
            {ATTR_ENTITY_ID: "update.update_unknown"},
            blocking=True,
        )


async def test_entity_with_specific_version(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update entity that support specific version."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    state = hass.states.get("update.update_specific_version")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.0.0"
    assert state.attributes[ATTR_LATEST_VERSION] == "1.0.0"

    # Update to a specific version
    await hass.services.async_call(
        DOMAIN,
        SERVICE_INSTALL,
        {ATTR_VERSION: "0.9.9", ATTR_ENTITY_ID: "update.update_specific_version"},
        blocking=True,
    )

    # Version has changed, state should be on as there is an update available
    state = hass.states.get("update.update_specific_version")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "0.9.9"
    assert state.attributes[ATTR_LATEST_VERSION] == "1.0.0"
    assert "Installed update with version: 0.9.9" in caplog.text

    # Update back to the latest version
    await hass.services.async_call(
        DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.update_specific_version"},
        blocking=True,
    )

    state = hass.states.get("update.update_specific_version")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.0.0"
    assert state.attributes[ATTR_LATEST_VERSION] == "1.0.0"
    assert "Installed latest update" in caplog.text

    # This entity does not support doing a backup before upgrade
    with pytest.raises(HomeAssistantError, match="Backup is not supported for"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_INSTALL,
            {
                ATTR_VERSION: "0.9.9",
                ATTR_BACKUP: True,
                ATTR_ENTITY_ID: "update.update_specific_version",
            },
            blocking=True,
        )


async def test_entity_with_backup_support(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update entity with backup support."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    # This entity support backing up before install the update
    state = hass.states.get("update.update_backup")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.0.0"
    assert state.attributes[ATTR_LATEST_VERSION] == "1.0.1"

    # Without a backup
    await hass.services.async_call(
        DOMAIN,
        SERVICE_INSTALL,
        {
            ATTR_BACKUP: False,
            ATTR_ENTITY_ID: "update.update_backup",
        },
        blocking=True,
    )

    state = hass.states.get("update.update_backup")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.0.1"
    assert state.attributes[ATTR_LATEST_VERSION] == "1.0.1"
    assert "Creating backup before installing update" not in caplog.text
    assert "Installed latest update" in caplog.text

    # Specific version, do create a backup this time
    await hass.services.async_call(
        DOMAIN,
        SERVICE_INSTALL,
        {
            ATTR_BACKUP: True,
            ATTR_VERSION: "0.9.8",
            ATTR_ENTITY_ID: "update.update_backup",
        },
        blocking=True,
    )

    # This entity support backing up before install the update
    state = hass.states.get("update.update_backup")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "0.9.8"
    assert state.attributes[ATTR_LATEST_VERSION] == "1.0.1"
    assert "Creating backup before installing update" in caplog.text
    assert "Installed update with version: 0.9.8" in caplog.text


async def test_entity_already_in_progress(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update install already in progress."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    state = hass.states.get("update.update_already_in_progress")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.0.0"
    assert state.attributes[ATTR_LATEST_VERSION] == "1.0.1"
    assert state.attributes[ATTR_IN_PROGRESS] == 50

    with pytest.raises(
        HomeAssistantError,
        match="Update installation already in progress for",
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: "update.update_already_in_progress"},
            blocking=True,
        )


async def test_entity_without_progress_support(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update entity without progress support.

    In that case, progress is still handled by Home Assistant.
    """
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    events = []
    async_track_state_change_event(
        hass, "update.update_available", callback(lambda event: events.append(event))
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.update_available"},
        blocking=True,
    )

    assert len(events) == 2
    assert events[0].data.get("old_state").attributes[ATTR_IN_PROGRESS] is False
    assert events[0].data.get("old_state").attributes[ATTR_INSTALLED_VERSION] == "1.0.0"
    assert events[0].data.get("new_state").attributes[ATTR_IN_PROGRESS] is True
    assert events[0].data.get("new_state").attributes[ATTR_INSTALLED_VERSION] == "1.0.0"

    assert events[1].data.get("old_state").attributes[ATTR_IN_PROGRESS] is True
    assert events[1].data.get("old_state").attributes[ATTR_INSTALLED_VERSION] == "1.0.0"
    assert events[1].data.get("new_state").attributes[ATTR_IN_PROGRESS] is False
    assert events[1].data.get("new_state").attributes[ATTR_INSTALLED_VERSION] == "1.0.1"


async def test_entity_without_progress_support_raising(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update entity without progress support that raises during install.

    In that case, progress is still handled by Home Assistant.
    """
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    events = []
    async_track_state_change_event(
        hass, "update.update_available", callback(lambda event: events.append(event))
    )

    with patch(
        "homeassistant.components.update.UpdateEntity.async_install",
        side_effect=RuntimeError,
    ), pytest.raises(RuntimeError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: "update.update_available"},
            blocking=True,
        )

    assert len(events) == 2
    assert events[0].data.get("old_state").attributes[ATTR_IN_PROGRESS] is False
    assert events[0].data.get("old_state").attributes[ATTR_INSTALLED_VERSION] == "1.0.0"
    assert events[0].data.get("new_state").attributes[ATTR_IN_PROGRESS] is True
    assert events[0].data.get("new_state").attributes[ATTR_INSTALLED_VERSION] == "1.0.0"

    assert events[1].data.get("old_state").attributes[ATTR_IN_PROGRESS] is True
    assert events[1].data.get("old_state").attributes[ATTR_INSTALLED_VERSION] == "1.0.0"
    assert events[1].data.get("new_state").attributes[ATTR_IN_PROGRESS] is False
    assert events[1].data.get("new_state").attributes[ATTR_INSTALLED_VERSION] == "1.0.0"


async def test_restore_state(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test we restore skipped version state."""
    mock_restore_cache(
        hass,
        (
            State(
                "update.update_available",
                STATE_ON,  # Incorrect, but helps checking if it is ignored
                {
                    ATTR_SKIPPED_VERSION: "1.0.1",
                },
            ),
        ),
    )

    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    state = hass.states.get("update.update_available")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.0.0"
    assert state.attributes[ATTR_LATEST_VERSION] == "1.0.1"
    assert state.attributes[ATTR_SKIPPED_VERSION] == "1.0.1"


async def test_release_notes(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    hass_ws_client: Callable[[HomeAssistant], Awaitable[ClientWebSocketResponse]],
) -> None:
    """Test getting the release notes over the websocket connection."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json(
        {
            "id": 1,
            "type": "update/release_notes",
            "entity_id": "update.update_with_release_notes",
        }
    )
    result = await client.receive_json()
    assert result["result"] == "Release notes"


async def test_release_notes_entity_not_found(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    hass_ws_client: Callable[[HomeAssistant], Awaitable[ClientWebSocketResponse]],
) -> None:
    """Test getting the release notes for not found entity."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json(
        {
            "id": 1,
            "type": "update/release_notes",
            "entity_id": "update.entity_not_found",
        }
    )
    result = await client.receive_json()
    assert result["error"]["code"] == "not_found"
    assert result["error"]["message"] == "Entity not found"


async def test_release_notes_entity_does_not_support_release_notes(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    hass_ws_client: Callable[[HomeAssistant], Awaitable[ClientWebSocketResponse]],
) -> None:
    """Test getting the release notes for entity that does not support release notes."""
    platform = getattr(hass.components, f"test.{DOMAIN}")
    platform.init()

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await hass.async_block_till_done()

    await client.send_json(
        {
            "id": 1,
            "type": "update/release_notes",
            "entity_id": "update.update_available",
        }
    )
    result = await client.receive_json()
    assert result["error"]["code"] == "not_supported"
    assert result["error"]["message"] == "Entity does not support release notes"
