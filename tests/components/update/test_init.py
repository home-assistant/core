"""The tests for the Update component."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from awesomeversion import AwesomeVersion, AwesomeVersionStrategy
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
    ATTR_DISPLAY_PRECISION,
    ATTR_IN_PROGRESS,
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    ATTR_RELEASE_SUMMARY,
    ATTR_RELEASE_URL,
    ATTR_SKIPPED_VERSION,
    ATTR_TITLE,
    ATTR_UPDATE_PERCENTAGE,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_ENTITY_PICTURE,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    CONF_PLATFORM,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    EntityCategory,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    MockEntityPlatform,
    MockModule,
    MockPlatform,
    mock_config_flow,
    mock_integration,
    mock_platform,
    mock_restore_cache,
    setup_test_component_platform,
)
from tests.typing import WebSocketGenerator

TEST_DOMAIN = "test"


class MockUpdateEntity(UpdateEntity):
    """Mock UpdateEntity to use in tests."""


async def test_update(hass: HomeAssistant) -> None:
    """Test getting data from the mocked update entity."""
    update = MockUpdateEntity()
    update.hass = hass
    update.platform = MockEntityPlatform(hass)

    update._attr_installed_version = "1.0.0"
    update._attr_latest_version = "1.0.1"
    update._attr_release_summary = "Summary"
    update._attr_release_url = "https://example.com"
    update._attr_title = "Title"

    assert update.entity_category is EntityCategory.DIAGNOSTIC
    assert (
        update.entity_picture
        == "https://brands.home-assistant.io/_/test_platform/icon.png"
    )
    assert update.installed_version == "1.0.0"
    assert update.latest_version == "1.0.1"
    assert update.release_summary == "Summary"
    assert update.release_url == "https://example.com"
    assert update.title == "Title"
    assert update.in_progress is False
    assert update.state == STATE_ON
    assert update.state_attributes == {
        ATTR_AUTO_UPDATE: False,
        ATTR_DISPLAY_PRECISION: 0,
        ATTR_INSTALLED_VERSION: "1.0.0",
        ATTR_IN_PROGRESS: False,
        ATTR_LATEST_VERSION: "1.0.1",
        ATTR_RELEASE_SUMMARY: "Summary",
        ATTR_RELEASE_URL: "https://example.com",
        ATTR_SKIPPED_VERSION: None,
        ATTR_TITLE: "Title",
        ATTR_UPDATE_PERCENTAGE: None,
    }

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
    del update.device_class
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
    mock_update_entities: list[MockUpdateEntity],
) -> None:
    """Test entity with no updates."""
    setup_test_component_platform(hass, DOMAIN, mock_update_entities)

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
    mock_update_entities: list[MockUpdateEntity],
) -> None:
    """Test entity with no updates."""
    setup_test_component_platform(hass, DOMAIN, mock_update_entities)

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
    mock_update_entities: list[MockUpdateEntity],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update entity that has auto update feature."""
    setup_test_component_platform(hass, DOMAIN, mock_update_entities)

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
        match="Skipping update is not supported for update.update_with_auto_update",
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
        match="Clearing skipped update is not supported for update.update_with_auto_update",
    ):
        await hass.services.async_call(
            DOMAIN,
            "clear_skipped",
            {ATTR_ENTITY_ID: "update.update_with_auto_update"},
            blocking=True,
        )


async def test_entity_with_updates_available(
    hass: HomeAssistant,
    mock_update_entities: list[MockUpdateEntity],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test basic update entity with updates available."""
    setup_test_component_platform(hass, DOMAIN, mock_update_entities)

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
    mock_update_entities: list[MockUpdateEntity],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update entity that has an unknown version."""
    setup_test_component_platform(hass, DOMAIN, mock_update_entities)

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
    mock_update_entities: list[MockUpdateEntity],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update entity that support specific version."""
    setup_test_component_platform(hass, DOMAIN, mock_update_entities)

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
    mock_update_entities: list[MockUpdateEntity],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update entity with backup support."""
    setup_test_component_platform(hass, DOMAIN, mock_update_entities)

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


@pytest.mark.parametrize(
    ("entity_id", "expected_display_precision", "expected_update_percentage"),
    [
        ("update.update_already_in_progress", 0, 50),
        ("update.update_already_in_progress_float", 2, 0.25),
    ],
)
async def test_entity_already_in_progress(
    hass: HomeAssistant,
    mock_update_entities: list[MockUpdateEntity],
    caplog: pytest.LogCaptureFixture,
    entity_id: str,
    expected_display_precision: int,
    expected_update_percentage: float,
) -> None:
    """Test update install already in progress."""
    setup_test_component_platform(hass, DOMAIN, mock_update_entities)

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_DISPLAY_PRECISION] == expected_display_precision
    assert state.attributes[ATTR_INSTALLED_VERSION] == "1.0.0"
    assert state.attributes[ATTR_LATEST_VERSION] == "1.0.1"
    assert state.attributes[ATTR_IN_PROGRESS] is True
    assert state.attributes[ATTR_UPDATE_PERCENTAGE] == expected_update_percentage

    with pytest.raises(
        HomeAssistantError,
        match="Update installation already in progress for",
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )


async def test_entity_without_progress_support(
    hass: HomeAssistant,
    mock_update_entities: list[MockUpdateEntity],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update entity without progress support.

    In that case, progress is still handled by Home Assistant.
    """
    setup_test_component_platform(hass, DOMAIN, mock_update_entities)

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    events = []
    async_track_state_change_event(
        hass,
        "update.update_available",
        # pylint: disable-next=unnecessary-lambda
        callback(lambda event: events.append(event)),
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
    mock_update_entities: list[MockUpdateEntity],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update entity without progress support that raises during install.

    In that case, progress is still handled by Home Assistant.
    """
    setup_test_component_platform(hass, DOMAIN, mock_update_entities)

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    events = []
    async_track_state_change_event(
        hass,
        "update.update_available",
        # pylint: disable-next=unnecessary-lambda
        callback(lambda event: events.append(event)),
    )

    with (
        patch(
            "homeassistant.components.update.UpdateEntity.async_install",
            side_effect=RuntimeError,
        ),
        pytest.raises(RuntimeError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: "update.update_available"},
            blocking=True,
        )

    await hass.async_block_till_done()

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
    hass: HomeAssistant, mock_update_entities: list[MockUpdateEntity]
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

    setup_test_component_platform(hass, DOMAIN, mock_update_entities)

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
    mock_update_entities: list[MockUpdateEntity],
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test getting the release notes over the websocket connection."""
    setup_test_component_platform(hass, DOMAIN, mock_update_entities)

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
    mock_update_entities: list[MockUpdateEntity],
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test getting the release notes for not found entity."""
    setup_test_component_platform(hass, DOMAIN, mock_update_entities)

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
    mock_update_entities: list[MockUpdateEntity],
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test getting the release notes for entity that does not support release notes."""
    setup_test_component_platform(hass, DOMAIN, mock_update_entities)

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


class MockFlow(ConfigFlow):
    """Test flow."""


@pytest.fixture(autouse=True)
def config_flow_fixture(hass: HomeAssistant) -> Generator[None]:
    """Mock config flow."""
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")

    with mock_config_flow(TEST_DOMAIN, MockFlow):
        yield


async def test_name(hass: HomeAssistant) -> None:
    """Test update name."""

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setups(config_entry, [DOMAIN])
        return True

    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")
    mock_integration(
        hass,
        MockModule(
            TEST_DOMAIN,
            async_setup_entry=async_setup_entry_init,
        ),
    )

    # Unnamed update entity without device class -> no name
    entity1 = UpdateEntity()
    entity1.entity_id = "update.test1"

    # Unnamed update entity with device class but has_entity_name False -> no name
    entity2 = UpdateEntity()
    entity2.entity_id = "update.test2"
    entity2._attr_device_class = UpdateDeviceClass.FIRMWARE

    # Unnamed update entity with device class and has_entity_name True -> named
    entity3 = UpdateEntity()
    entity3.entity_id = "update.test3"
    entity3._attr_device_class = UpdateDeviceClass.FIRMWARE
    entity3._attr_has_entity_name = True

    # Unnamed update entity with device class and has_entity_name True -> named
    entity4 = UpdateEntity()
    entity4.entity_id = "update.test4"
    entity4.entity_description = UpdateEntityDescription(
        "test",
        UpdateDeviceClass.FIRMWARE,
        has_entity_name=True,
    )

    async def async_setup_entry_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up test update platform via config entry."""
        async_add_entities([entity1, entity2, entity3, entity4])

    mock_platform(
        hass,
        f"{TEST_DOMAIN}.{DOMAIN}",
        MockPlatform(async_setup_entry=async_setup_entry_platform),
    )

    config_entry = MockConfigEntry(domain=TEST_DOMAIN)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity1.entity_id)
    assert state
    assert "device_class" not in state.attributes
    assert "friendly_name" not in state.attributes

    state = hass.states.get(entity2.entity_id)
    assert state
    assert state.attributes.get("device_class") == "firmware"
    assert "friendly_name" not in state.attributes

    expected = {
        "device_class": "firmware",
        "friendly_name": "Firmware",
    }
    state = hass.states.get(entity3.entity_id)
    assert state
    assert expected.items() <= state.attributes.items()

    state = hass.states.get(entity4.entity_id)
    assert state
    assert expected.items() <= state.attributes.items()


def test_deprecated_supported_features_ints(caplog: pytest.LogCaptureFixture) -> None:
    """Test deprecated supported features ints."""

    class MockUpdateEntity(UpdateEntity):
        @property
        def supported_features(self) -> int:
            """Return supported features."""
            return 1

    entity = MockUpdateEntity()
    assert entity.supported_features_compat is UpdateEntityFeature(1)
    assert "MockUpdateEntity" in caplog.text
    assert "is using deprecated supported features values" in caplog.text
    assert "Instead it should use" in caplog.text
    assert "UpdateEntityFeature.INSTALL" in caplog.text
    caplog.clear()
    assert entity.supported_features_compat is UpdateEntityFeature(1)
    assert "is using deprecated supported features values" not in caplog.text


async def test_deprecated_supported_features_ints_with_service_call(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test deprecated supported features ints with install service."""

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setups(config_entry, [DOMAIN])
        return True

    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")
    mock_integration(
        hass,
        MockModule(
            TEST_DOMAIN,
            async_setup_entry=async_setup_entry_init,
        ),
    )

    class MockUpdateEntity(UpdateEntity):
        _attr_supported_features = 1 | 2

        def install(self, version: str | None = None, backup: bool = False) -> None:
            """Install an update."""

    entity = MockUpdateEntity()
    entity.entity_id = (
        "update.test_deprecated_supported_features_ints_with_service_call"
    )

    async def async_setup_entry_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Set up test update platform via config entry."""
        async_add_entities([entity])

    mock_platform(
        hass,
        f"{TEST_DOMAIN}.{DOMAIN}",
        MockPlatform(async_setup_entry=async_setup_entry_platform),
    )

    config_entry = MockConfigEntry(domain=TEST_DOMAIN)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert "is using deprecated supported features values" in caplog.text

    assert isinstance(entity.supported_features, int)

    with pytest.raises(
        HomeAssistantError,
        match="Backup is not supported for update.test_deprecated_supported_features_ints_with_service_call",
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_INSTALL,
            {
                ATTR_VERSION: "0.9.9",
                ATTR_BACKUP: True,
                ATTR_ENTITY_ID: "update.test_deprecated_supported_features_ints_with_service_call",
            },
            blocking=True,
        )


async def test_custom_version_is_newer(hass: HomeAssistant) -> None:
    """Test UpdateEntity with overridden version_is_newer method."""

    class MockUpdateEntity(UpdateEntity):
        def version_is_newer(self, latest_version: str, installed_version: str) -> bool:
            """Return True if latest_version is newer than installed_version."""
            return AwesomeVersion(
                latest_version,
                find_first_match=True,
                ensure_strategy=[AwesomeVersionStrategy.SEMVER],
            ) > AwesomeVersion(
                installed_version,
                find_first_match=True,
                ensure_strategy=[AwesomeVersionStrategy.SEMVER],
            )

    update = MockUpdateEntity()
    update.hass = hass
    update.platform = MockEntityPlatform(hass)

    STABLE = "20230913-111730/v1.14.0-gcb84623"
    BETA = "20231107-162609/v1.14.1-rc1-g0617c15"

    # Set current installed version to STABLE
    update._attr_installed_version = STABLE
    update._attr_latest_version = BETA

    assert update.installed_version == STABLE
    assert update.latest_version == BETA
    assert update.state == STATE_ON

    # Set current installed version to BETA
    update._attr_installed_version = BETA
    update._attr_latest_version = STABLE

    assert update.installed_version == BETA
    assert update.latest_version == STABLE
    assert update.state == STATE_OFF


@pytest.mark.parametrize(
    ("supported_features", "extra_expected_attributes"),
    [
        (
            0,
            [
                {},
                {},
                {},
                {},
                {},
                {},
                {},
            ],
        ),
        (
            UpdateEntityFeature.PROGRESS,
            [
                {ATTR_IN_PROGRESS: False},
                {ATTR_IN_PROGRESS: False},
                {ATTR_IN_PROGRESS: True, ATTR_UPDATE_PERCENTAGE: 0},
                {ATTR_IN_PROGRESS: True},
                {ATTR_IN_PROGRESS: True, ATTR_UPDATE_PERCENTAGE: 1},
                {ATTR_IN_PROGRESS: True, ATTR_UPDATE_PERCENTAGE: 10},
                {ATTR_IN_PROGRESS: True, ATTR_UPDATE_PERCENTAGE: 100},
            ],
        ),
    ],
)
async def test_update_percentage_backwards_compatibility(
    hass: HomeAssistant,
    supported_features: UpdateEntityFeature,
    extra_expected_attributes: list[dict],
) -> None:
    """Test deriving update percentage from deprecated in_progress."""
    update = MockUpdateEntity()

    update._attr_installed_version = "1.0.0"
    update._attr_latest_version = "1.0.1"
    update._attr_name = "legacy"
    update._attr_release_summary = "Summary"
    update._attr_release_url = "https://example.com"
    update._attr_supported_features = supported_features
    update._attr_title = "Title"

    setup_test_component_platform(hass, DOMAIN, [update])
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    expected_attributes = {
        ATTR_AUTO_UPDATE: False,
        ATTR_DISPLAY_PRECISION: 0,
        ATTR_ENTITY_PICTURE: "https://brands.home-assistant.io/_/test/icon.png",
        ATTR_FRIENDLY_NAME: "legacy",
        ATTR_INSTALLED_VERSION: "1.0.0",
        ATTR_IN_PROGRESS: False,
        ATTR_LATEST_VERSION: "1.0.1",
        ATTR_RELEASE_SUMMARY: "Summary",
        ATTR_RELEASE_URL: "https://example.com",
        ATTR_SKIPPED_VERSION: None,
        ATTR_SUPPORTED_FEATURES: supported_features,
        ATTR_TITLE: "Title",
        ATTR_UPDATE_PERCENTAGE: None,
    }

    state = hass.states.get("update.legacy")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes == expected_attributes | extra_expected_attributes[0]

    in_progress_list = [False, 0, True, 1, 10, 100]

    for i, in_progress in enumerate(in_progress_list):
        update._attr_in_progress = in_progress
        update.async_write_ha_state()
        state = hass.states.get("update.legacy")
        assert state.state == STATE_ON
        assert (
            state.attributes == expected_attributes | extra_expected_attributes[i + 1]
        )
