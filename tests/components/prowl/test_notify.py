"""Test the Prowl notifications."""

from typing import Any
from unittest.mock import AsyncMock

import prowlpy
import pytest

from homeassistant.components import notify
from homeassistant.components.prowl.const import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from .conftest import ENTITY_ID, OTHER_API_KEY, TEST_API_KEY, TEST_NAME, TEST_SERVICE
from .helpers import get_config_entry

from tests.common import MockConfigEntry

SERVICE_DATA = {"message": "Test Notification", "title": "Test Title"}

EXPECTED_SEND_PARAMETERS = {
    "application": "Home-Assistant",
    "event": "Test Title",
    "description": "Test Notification",
    "priority": 0,
    "url": None,
}


@pytest.mark.usefixtures("configure_prowl_through_yaml")
async def test_send_notification_service(
    hass: HomeAssistant,
    mock_prowlpy: AsyncMock,
) -> None:
    """Set up Prowl, call notify service, and check API call."""
    assert hass.services.has_service(notify.DOMAIN, TEST_SERVICE)
    await hass.services.async_call(
        notify.DOMAIN,
        TEST_SERVICE,
        SERVICE_DATA,
        blocking=True,
    )

    mock_prowlpy.post.assert_called_once_with(**EXPECTED_SEND_PARAMETERS)


async def test_send_notification_entity_service(
    hass: HomeAssistant,
    mock_prowlpy: AsyncMock,
    mock_prowlpy_config_entry: MockConfigEntry,
) -> None:
    """Set up Prowl via config entry, call notify service, and check API call."""
    mock_prowlpy_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_prowlpy_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service(notify.DOMAIN, notify.SERVICE_SEND_MESSAGE)
    await hass.services.async_call(
        notify.DOMAIN,
        notify.SERVICE_SEND_MESSAGE,
        {
            "entity_id": ENTITY_ID,
            notify.ATTR_MESSAGE: SERVICE_DATA["message"],
            notify.ATTR_TITLE: SERVICE_DATA["title"],
        },
        blocking=True,
    )

    mock_prowlpy.post.assert_called_once_with(**EXPECTED_SEND_PARAMETERS)


@pytest.mark.parametrize(
    ("prowlpy_side_effect", "raised_exception", "exception_message"),
    [
        (
            prowlpy.APIError("Internal server error"),
            HomeAssistantError,
            "Unexpected error when calling Prowl API",
        ),
        (
            TimeoutError,
            HomeAssistantError,
            "Timeout accessing Prowl API",
        ),
        (
            prowlpy.InvalidAPIKeyError(f"Invalid API key: {TEST_API_KEY}"),
            HomeAssistantError,
            "Invalid API key for Prowl service",
        ),
        (
            prowlpy.RateLimitExceededError(
                "Not accepted: Your IP address has exceeded the API limit"
            ),
            HomeAssistantError,
            "Prowl service reported: exceeded rate limit",
        ),
        (
            SyntaxError(),
            SyntaxError,
            None,
        ),
    ],
)
async def test_fail_send_notification_entity_service(
    hass: HomeAssistant,
    mock_prowlpy: AsyncMock,
    mock_prowlpy_config_entry: MockConfigEntry,
    prowlpy_side_effect: Exception,
    raised_exception: type[Exception],
    exception_message: str | None,
) -> None:
    """Set up Prowl via config entry, call notify service, and check API call."""
    mock_prowlpy_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_prowlpy_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_prowlpy.post.side_effect = prowlpy_side_effect

    assert hass.services.has_service(notify.DOMAIN, notify.SERVICE_SEND_MESSAGE)
    with pytest.raises(raised_exception, match=exception_message):
        await hass.services.async_call(
            notify.DOMAIN,
            notify.SERVICE_SEND_MESSAGE,
            {
                "entity_id": ENTITY_ID,
                notify.ATTR_MESSAGE: SERVICE_DATA["message"],
                notify.ATTR_TITLE: SERVICE_DATA["title"],
            },
            blocking=True,
        )

    mock_prowlpy.post.assert_called_once_with(**EXPECTED_SEND_PARAMETERS)


@pytest.mark.parametrize(
    ("prowlpy_side_effect", "raised_exception", "exception_message"),
    [
        (
            prowlpy.APIError("Internal server error"),
            HomeAssistantError,
            "Unexpected error when calling Prowl API",
        ),
        (
            TimeoutError,
            HomeAssistantError,
            "Timeout accessing Prowl API",
        ),
        (
            prowlpy.InvalidAPIKeyError(f"Invalid API key: {TEST_API_KEY}"),
            HomeAssistantError,
            "Invalid API key for Prowl service",
        ),
        (
            prowlpy.RateLimitExceededError(
                "Not accepted: Your IP address has exceeded the API limit"
            ),
            HomeAssistantError,
            "Prowl service reported: exceeded rate limit",
        ),
        (
            SyntaxError(),
            SyntaxError,
            None,
        ),
    ],
)
@pytest.mark.usefixtures("configure_prowl_through_yaml")
async def test_fail_send_notification(
    hass: HomeAssistant,
    mock_prowlpy: AsyncMock,
    prowlpy_side_effect: Exception,
    raised_exception: type[Exception],
    exception_message: str | None,
) -> None:
    """Sending a message via Prowl with a failure."""
    mock_prowlpy.post.side_effect = prowlpy_side_effect

    assert hass.services.has_service(notify.DOMAIN, TEST_SERVICE)
    with pytest.raises(raised_exception, match=exception_message):
        await hass.services.async_call(
            notify.DOMAIN,
            TEST_SERVICE,
            SERVICE_DATA,
            blocking=True,
        )

    mock_prowlpy.post.assert_called_once_with(**EXPECTED_SEND_PARAMETERS)


@pytest.mark.parametrize(
    ("service_data", "expected_send_parameters"),
    [
        (
            {"message": "Test Notification", "title": "Test Title"},
            {
                "application": "Home-Assistant",
                "event": "Test Title",
                "description": "Test Notification",
                "priority": 0,
                "url": None,
            },
        )
    ],
)
@pytest.mark.usefixtures("configure_prowl_through_yaml")
async def test_other_exception_send_notification(
    hass: HomeAssistant,
    mock_prowlpy: AsyncMock,
    service_data: dict[str, Any],
    expected_send_parameters: dict[str, Any],
) -> None:
    """Sending a message via Prowl with a general unhandled exception."""
    mock_prowlpy.post.side_effect = SyntaxError

    assert hass.services.has_service(notify.DOMAIN, TEST_SERVICE)
    with pytest.raises(SyntaxError):
        await hass.services.async_call(
            notify.DOMAIN,
            TEST_SERVICE,
            SERVICE_DATA,
            blocking=True,
        )

    mock_prowlpy.post.assert_called_once_with(**expected_send_parameters)


@pytest.mark.usefixtures("configure_prowl_through_yaml")
async def test_yaml_migration_creates_config_entry(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """Test that YAML configuration triggers config entry creation."""
    entry = get_config_entry(hass, TEST_API_KEY, config_method="import")

    assert entry is not None, "No import config entry found"
    assert entry.data[CONF_API_KEY] == TEST_API_KEY
    assert entry.title == TEST_NAME

    issue = issue_registry.async_get_issue(DOMAIN, "deprecated_yaml_prowl")

    assert issue is not None, "No issue found for YAML deprecation"
    assert issue.translation_key == "prowl_yaml_deprecated"
    assert issue.severity == ir.IssueSeverity.WARNING


async def test_yaml_migration_with_bad_key(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry, mock_prowlpy: AsyncMock
) -> None:
    """Test that YAML configuration with bad API key creates issue but no config entry."""
    mock_prowlpy.verify_key.side_effect = prowlpy.InvalidAPIKeyError

    await async_setup_component(
        hass,
        notify.DOMAIN,
        {
            notify.DOMAIN: [
                {
                    "name": TEST_NAME,
                    "platform": DOMAIN,
                    "api_key": "invalid_key",
                },
            ]
        },
    )
    await hass.async_block_till_done()

    entry = get_config_entry(hass, "invalid_key", config_method="import")
    assert entry is None, "Config entry should not be created with invalid API key"

    issue = issue_registry.async_get_issue(DOMAIN, "migrate_fail_prowl")

    assert issue is not None, "No issue found for failed YAML migration"
    assert issue.translation_key == "prowl_yaml_migration_fail"
    assert issue.severity == ir.IssueSeverity.WARNING


@pytest.mark.usefixtures("configure_prowl_through_yaml")
async def test_yaml_migration_creates_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that YAML configuration creates a repair issue."""
    issue = issue_registry.async_get_issue(DOMAIN, f"deprecated_yaml_{DOMAIN}")
    assert issue is not None
    assert issue.translation_key == "prowl_yaml_deprecated"
    assert issue.severity == ir.IssueSeverity.WARNING


@pytest.mark.usefixtures("mock_prowlpy")
async def test_yaml_migration_migrates_all_entries(
    hass: HomeAssistant,
) -> None:
    """Test that multiple YAML setups all get migrated."""
    await async_setup_component(
        hass,
        notify.DOMAIN,
        {
            notify.DOMAIN: [
                {
                    "name": DOMAIN,
                    "platform": DOMAIN,
                    "api_key": TEST_API_KEY,
                },
                {
                    "name": f"{DOMAIN}_2",
                    "platform": DOMAIN,
                    "api_key": OTHER_API_KEY,
                },
            ]
        },
    )
    await hass.async_block_till_done()
    entry = get_config_entry(hass, TEST_API_KEY, config_method="import")

    assert entry is not None, "First import config entry not found"
    assert entry.data[CONF_API_KEY] == TEST_API_KEY

    entry = get_config_entry(hass, OTHER_API_KEY, config_method="import")

    assert entry is not None, "Second import config entry not found"
    assert entry.data[CONF_API_KEY] == OTHER_API_KEY


async def test_yaml_migration_does_not_duplicate_config_entry(
    hass: HomeAssistant,
    mock_prowlpy_config_entry: MockConfigEntry,
) -> None:
    """Test that we don't create duplicates when migrating YAML entities if there are existing ConfigEntries."""
    mock_prowlpy_config_entry.add_to_hass(hass)

    entries_before = [
        e
        for e in hass.config_entries.async_entries(DOMAIN)
        if e.data.get(CONF_API_KEY) == TEST_API_KEY
    ]

    await async_setup_component(
        hass,
        notify.DOMAIN,
        {
            notify.DOMAIN: [
                {
                    "name": TEST_NAME,
                    "platform": DOMAIN,
                    "api_key": TEST_API_KEY,
                },
            ]
        },
    )
    await hass.async_block_till_done()

    entries_after = [
        e
        for e in hass.config_entries.async_entries(DOMAIN)
        if e.data.get(CONF_API_KEY) == TEST_API_KEY
    ]
    assert len(entries_after) == len(entries_before), (
        "Duplicate config entry was created"
    )
    assert mock_prowlpy_config_entry in entries_after, "Config entry was not created"


@pytest.mark.usefixtures("configure_prowl_through_yaml")
async def test_legacy_notify_service_creates_migration_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that calling legacy notify service creates migration issue."""
    await hass.services.async_call(
        notify.DOMAIN,
        TEST_SERVICE,
        SERVICE_DATA,
        blocking=True,
    )

    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(notify.DOMAIN, "migrate_notify_prowl_prowl")

    assert issue is not None
    assert issue.translation_key == "migrate_notify_service"
    assert issue.severity == ir.IssueSeverity.WARNING
