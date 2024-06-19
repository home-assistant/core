"""Tests for the seventeentrack sensor."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from py17track.errors import SeventeenTrackError

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from . import goto_future, init_integration
from .conftest import (
    DEFAULT_SUMMARY,
    DEFAULT_SUMMARY_LENGTH,
    NEW_SUMMARY_DATA,
    VALID_PLATFORM_CONFIG_FULL,
    get_package,
)

from tests.common import MockConfigEntry


async def test_full_valid_config(
    hass: HomeAssistant,
    mock_seventeentrack: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure everything starts correctly."""
    await init_integration(hass, mock_config_entry)
    assert len(hass.states.async_entity_ids()) == len(DEFAULT_SUMMARY.keys())


async def test_valid_config(
    hass: HomeAssistant,
    mock_seventeentrack: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure everything starts correctly."""
    await init_integration(hass, mock_config_entry)
    assert len(hass.states.async_entity_ids()) == len(DEFAULT_SUMMARY.keys())


async def test_invalid_config(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Ensure nothing is created when config is wrong."""
    await init_integration(hass, mock_config_entry)
    assert not hass.states.async_entity_ids("sensor")


async def test_login_exception(
    hass: HomeAssistant,
    mock_seventeentrack: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure everything starts correctly."""
    mock_seventeentrack.return_value.profile.login.side_effect = SeventeenTrackError(
        "Error"
    )
    await init_integration(hass, mock_config_entry)
    assert not hass.states.async_entity_ids("sensor")


async def test_add_package(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_seventeentrack: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure package is added correctly when user add a new package."""
    package = get_package()
    mock_seventeentrack.return_value.profile.packages.return_value = [package]

    await init_integration(hass, mock_config_entry)
    assert hass.states.get("sensor.17track_package_friendly_name_1")
    assert len(hass.states.async_entity_ids()) == DEFAULT_SUMMARY_LENGTH + 1

    package2 = get_package(
        tracking_number="789",
        friendly_name="friendly name 2",
        info_text="info text 2",
        location="location 2",
        timestamp="2020-08-10 14:25",
    )
    mock_seventeentrack.return_value.profile.packages.return_value = [package, package2]

    await goto_future(hass, freezer)

    assert hass.states.get("sensor.17track_package_friendly_name_1") is not None
    assert len(hass.states.async_entity_ids()) == DEFAULT_SUMMARY_LENGTH + 2


async def test_add_package_default_friendly_name(
    hass: HomeAssistant,
    mock_seventeentrack: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure package is added correctly with default friendly name when user add a new package without his own friendly name."""
    package = get_package(friendly_name=None)
    mock_seventeentrack.return_value.profile.packages.return_value = [package]

    await init_integration(hass, mock_config_entry)
    state_456 = hass.states.get("sensor.17track_package_456")
    assert state_456 is not None
    assert state_456.attributes["friendly_name"] == "17Track Package 456"
    assert len(hass.states.async_entity_ids()) == DEFAULT_SUMMARY_LENGTH + 1


async def test_remove_package(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_seventeentrack: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure entity is not there anymore if package is not there."""
    package1 = get_package()
    package2 = get_package(
        tracking_number="789",
        friendly_name="friendly name 2",
        info_text="info text 2",
        location="location 2",
        timestamp="2020-08-10 14:25",
    )

    mock_seventeentrack.return_value.profile.packages.return_value = [
        package1,
        package2,
    ]

    await init_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.17track_package_friendly_name_1") is not None
    assert hass.states.get("sensor.17track_package_friendly_name_2") is not None
    assert len(hass.states.async_entity_ids()) == DEFAULT_SUMMARY_LENGTH + 2

    mock_seventeentrack.return_value.profile.packages.return_value = [package2]

    await goto_future(hass, freezer)

    assert hass.states.get("sensor.17track_package_friendly_name_1") is None
    assert hass.states.get("sensor.17track_package_friendly_name_2") is not None
    assert len(hass.states.async_entity_ids()) == DEFAULT_SUMMARY_LENGTH + 1


async def test_package_error(
    hass: HomeAssistant,
    mock_seventeentrack: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure package is added correctly when user add a new package."""
    mock_seventeentrack.return_value.profile.packages.side_effect = SeventeenTrackError(
        "Error"
    )
    mock_seventeentrack.return_value.profile.summary.return_value = {}

    await init_integration(hass, mock_config_entry)
    assert hass.states.get("sensor.17track_package_friendly_name_1") is None


async def test_delivered_not_shown(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_seventeentrack: AsyncMock,
    mock_config_entry_with_default_options: MockConfigEntry,
) -> None:
    """Ensure delivered packages are not shown."""
    package = get_package(status=40)
    mock_seventeentrack.return_value.profile.packages.return_value = [package]

    with patch(
        "homeassistant.components.seventeentrack.sensor.persistent_notification"
    ) as persistent_notification_mock:
        await init_integration(hass, mock_config_entry_with_default_options)
        await goto_future(hass, freezer)

        assert hass.states.get("sensor.17track_package_friendly_name_1") is None
        persistent_notification_mock.create.assert_called()


async def test_delivered_shown(
    hass: HomeAssistant,
    mock_seventeentrack: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure delivered packages are show when user choose to show them."""
    package = get_package(status=40)
    mock_seventeentrack.return_value.profile.packages.return_value = [package]

    with patch(
        "homeassistant.components.seventeentrack.sensor.persistent_notification"
    ) as persistent_notification_mock:
        await init_integration(hass, mock_config_entry)

        assert hass.states.get("sensor.17track_package_friendly_name_1") is not None
        assert len(hass.states.async_entity_ids()) == DEFAULT_SUMMARY_LENGTH + 1
        persistent_notification_mock.create.assert_not_called()


async def test_becomes_delivered_not_shown_notification(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_seventeentrack: AsyncMock,
    mock_config_entry_with_default_options: MockConfigEntry,
) -> None:
    """Ensure notification is triggered when package becomes delivered."""
    package = get_package()
    mock_seventeentrack.return_value.profile.packages.return_value = [package]

    await init_integration(hass, mock_config_entry_with_default_options)

    assert hass.states.get("sensor.17track_package_friendly_name_1") is not None
    assert len(hass.states.async_entity_ids()) == DEFAULT_SUMMARY_LENGTH + 1

    package_delivered = get_package(status=40)
    mock_seventeentrack.return_value.profile.packages.return_value = [package_delivered]

    with patch(
        "homeassistant.components.seventeentrack.sensor.persistent_notification"
    ) as persistent_notification_mock:
        await goto_future(hass, freezer)

        persistent_notification_mock.create.assert_called()
        assert len(hass.states.async_entity_ids()) == DEFAULT_SUMMARY_LENGTH


async def test_summary_correctly_updated(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_seventeentrack: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure summary entities are not duplicated."""
    package = get_package(status=30)
    mock_seventeentrack.return_value.profile.packages.return_value = [package]

    await init_integration(hass, mock_config_entry)

    assert len(hass.states.async_entity_ids()) == DEFAULT_SUMMARY_LENGTH + 1

    state_ready_picked = hass.states.get("sensor.17track_ready_to_be_picked_up")
    assert state_ready_picked is not None
    assert len(state_ready_picked.attributes["packages"]) == 1

    mock_seventeentrack.return_value.profile.packages.return_value = []
    mock_seventeentrack.return_value.profile.summary.return_value = NEW_SUMMARY_DATA

    await goto_future(hass, freezer)

    assert len(hass.states.async_entity_ids()) == len(NEW_SUMMARY_DATA)
    for state in hass.states.async_all():
        assert state.state == "1"

    state_ready_picked = hass.states.get("sensor.17track_ready_to_be_picked_up")
    assert state_ready_picked is not None
    assert len(state_ready_picked.attributes["packages"]) == 0


async def test_summary_error(
    hass: HomeAssistant,
    mock_seventeentrack: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test summary empty if error."""
    package = get_package(status=30)
    mock_seventeentrack.return_value.profile.packages.return_value = [package]
    mock_seventeentrack.return_value.profile.summary.side_effect = SeventeenTrackError(
        "Error"
    )

    await init_integration(hass, mock_config_entry)

    assert len(hass.states.async_entity_ids()) == 0

    assert (
        hass.states.get("sensor.seventeentrack_packages_ready_to_be_picked_up") is None
    )


async def test_utc_timestamp(
    hass: HomeAssistant,
    mock_seventeentrack: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure package timestamp is converted correctly from HA-defined time zone to UTC."""

    package = get_package(tz="Asia/Jakarta")
    mock_seventeentrack.return_value.profile.packages.return_value = [package]

    await init_integration(hass, mock_config_entry)

    assert hass.states.get("sensor.17track_package_friendly_name_1") is not None
    assert len(hass.states.async_entity_ids()) == DEFAULT_SUMMARY_LENGTH + 1
    state_456 = hass.states.get("sensor.17track_package_friendly_name_1")
    assert state_456 is not None
    assert str(state_456.attributes.get("timestamp")) == "2020-08-10 03:32:00+00:00"


async def test_non_valid_platform_config(
    hass: HomeAssistant, mock_seventeentrack: AsyncMock
) -> None:
    """Test if login fails."""
    mock_seventeentrack.return_value.profile.login.return_value = False
    assert await async_setup_component(hass, "sensor", VALID_PLATFORM_CONFIG_FULL)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids()) == 0


async def test_full_valid_platform_config(
    hass: HomeAssistant,
    mock_seventeentrack: AsyncMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Ensure everything starts correctly."""
    assert await async_setup_component(hass, "sensor", VALID_PLATFORM_CONFIG_FULL)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids()) == len(DEFAULT_SUMMARY.keys())
    assert len(issue_registry.issues) == 1
