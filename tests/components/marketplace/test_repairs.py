"""Tests for the Marketplace repairs."""

import asyncio
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.marketplace.base import MarketplaceManager
from homeassistant.components.marketplace.const import DOMAIN, STORAGE_VERSION
from homeassistant.components.marketplace.critical import (
    async_create_critical_repository_issue,
)
from homeassistant.components.marketplace.exceptions import (
    MarketplaceError,
    NotModifiedError,
)
from homeassistant.components.marketplace.repairs import async_create_fix_flow
from homeassistant.components.marketplace.utils.storage import (
    async_load_from_storage,
    async_save_to_storage,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from . import setup_integration
from .const import REPOSITORY_INTEGRATION, REPOSITORY_INTEGRATION_ID

from tests.common import MockConfigEntry, async_mock_service
from tests.components.repairs import process_repair_fix_flow, start_repair_fix_flow
from tests.typing import ClientSessionGenerator

ISSUE_ID = f"restart_required_{REPOSITORY_INTEGRATION_ID}_1.0.0"


async def test_restart_required_fix_flow(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    marketplace: MarketplaceManager,
) -> None:
    """Test restarting Home Assistant from the repair."""
    assert await async_setup_component(hass, "repairs", {})
    restarts = async_mock_service(hass, "homeassistant", "restart")

    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_ID,
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="restart_required",
        translation_placeholders={"name": "Basic integration"},
    )

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, ISSUE_ID)

    assert data["step_id"] == "confirm_restart"
    assert data["description_placeholders"] == {"name": "Basic integration"}

    data = await process_repair_fix_flow(client, data["flow_id"])

    assert data["type"] == "create_entry"
    assert len(restarts) == 1
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is None


async def test_restart_required_fix_flow_for_an_unknown_repository(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    marketplace: MarketplaceManager,
) -> None:
    """Test the repair of a repository the Marketplace no longer knows."""
    assert await async_setup_component(hass, "repairs", {})
    issue_id = "restart_required_0_1.0.0"

    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="restart_required",
        translation_placeholders={"name": "Unknown integration"},
    )

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, issue_id)

    assert data["step_id"] == "confirm_restart"
    assert data["description_placeholders"] == {"name": "Unknown integration"}


async def test_restart_required_fix_flow_while_unloaded(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    marketplace: MarketplaceManager,
) -> None:
    """Test the repair still opens when the Marketplace is not loaded."""
    assert await async_setup_component(hass, "repairs", {})
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_ID,
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="restart_required",
        translation_placeholders={"name": "Basic integration"},
    )
    assert marketplace.configuration.config_entry is not None
    assert await hass.config_entries.async_unload(
        marketplace.configuration.config_entry.entry_id
    )

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, ISSUE_ID)

    assert data["step_id"] == "confirm_restart"
    assert data["description_placeholders"] == {"name": "Basic integration"}


async def test_removal_the_catalog_takes_back(
    hass: HomeAssistant,
    marketplace: MarketplaceManager,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a repository back in the catalog is no longer held as removed."""
    repository = marketplace.repositories.get_by_id(REPOSITORY_INTEGRATION_ID)
    repository.data.installed = True
    removal = {
        "repository": REPOSITORY_INTEGRATION,
        "removal_type": "remove",
        "reason": "Not maintained",
    }

    with (
        patch.object(
            marketplace.data_client,
            "async_get_removed",
            side_effect=[[removal], []],
        ),
        patch.object(marketplace.data, "async_write"),
    ):
        await marketplace.async_handle_removed_repositories()
        assert marketplace.repositories.is_removed(REPOSITORY_INTEGRATION)
        assert issue_registry.async_get_issue(
            DOMAIN, f"removed_{REPOSITORY_INTEGRATION_ID}"
        )

        await marketplace.async_handle_removed_repositories()

    assert not marketplace.repositories.is_removed(REPOSITORY_INTEGRATION)
    assert not issue_registry.async_get_issue(
        DOMAIN, f"removed_{REPOSITORY_INTEGRATION_ID}"
    )


async def test_critical_removal_stays_when_the_removals_change(
    marketplace: MarketplaceManager,
) -> None:
    """Test a critical removal is not forgotten, it comes from its own feed."""
    marketplace.repositories.removed_repository(
        REPOSITORY_INTEGRATION
    ).removal_type = "critical"

    with patch.object(marketplace.data_client, "async_get_removed", return_value=[]):
        await marketplace.async_handle_removed_repositories()

    assert marketplace.repositories.is_removed(REPOSITORY_INTEGRATION)


@pytest.mark.parametrize(
    ("feed", "method", "handler"),
    [
        pytest.param(
            "removed",
            "async_get_removed",
            "async_handle_removed_repositories",
            id="removed",
        ),
        pytest.param(
            "critical",
            "async_get_critical",
            "async_handle_critical_repositories",
            id="critical",
        ),
    ],
)
async def test_feed_that_can_not_be_reached_is_told_once(
    marketplace: MarketplaceManager,
    caplog: pytest.LogCaptureFixture,
    feed: str,
    method: str,
    handler: str,
) -> None:
    """Test a feed that fails is logged once and once back, never as empty."""
    with (
        patch.object(
            marketplace.data_client,
            method,
            side_effect=MarketplaceError("no route to host"),
        ),
        patch.object(marketplace.data, "async_write"),
    ):
        # Once to go away, once more that is not news anymore
        for _ in range(2):
            await getattr(marketplace, handler)()

    assert marketplace.unreachable_feeds == {feed}
    assert "No critical repositories" not in caplog.text

    with (
        patch.object(marketplace.data_client, method, return_value=[]),
        patch.object(marketplace.data, "async_write"),
    ):
        await getattr(marketplace, handler)()

    assert not marketplace.unreachable_feeds
    assert [
        record.getMessage()
        for record in caplog.records
        if record.levelname == "INFO" and f"{feed} feed" in record.getMessage()
    ] == [
        f"The {feed} feed can not be reached: no route to host",
        f"The {feed} feed can be reached again",
    ]


async def test_no_fix_flow_for_other_issues(hass: HomeAssistant) -> None:
    """Test that only the restart issue is fixable."""
    assert await async_create_fix_flow(hass, "removed_1296269", None) is None


CRITICAL_REPOSITORY = {
    "repository": REPOSITORY_INTEGRATION,
    "reason": "It removes your configuration",
    "link": "https://github.com/hacs/default/issues/1",
}
CRITICAL_ISSUE_ID = f"critical_repository_{REPOSITORY_INTEGRATION}"


async def test_critical_repository_removal_creates_an_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    marketplace: MarketplaceManager,
) -> None:
    """Test a repository removed for being critical is explained in a repair."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    repository.data.installed = True

    with (
        patch.object(
            marketplace.data_client,
            "async_get_critical",
            return_value=[CRITICAL_REPOSITORY],
        ),
        patch.object(repository, "uninstall") as uninstall,
        patch.object(hass, "async_stop") as stop,
    ):
        await marketplace.async_handle_critical_repositories()
        await hass.async_block_till_done()

    uninstall.assert_called_once()
    stop.assert_called_once_with(100)

    issue = issue_registry.async_get_issue(DOMAIN, CRITICAL_ISSUE_ID)
    assert issue is not None
    assert issue.is_persistent
    assert issue.is_fixable
    assert issue.severity is ir.IssueSeverity.CRITICAL
    assert issue.learn_more_url == CRITICAL_REPOSITORY["link"]
    assert issue.translation_placeholders == {
        "repository": REPOSITORY_INTEGRATION,
        "reason": CRITICAL_REPOSITORY["reason"],
    }
    assert not hass.states.async_all("persistent_notification")


@pytest.mark.parametrize(
    ("acknowledged", "has_issue"),
    [
        pytest.param(False, True, id="not_acknowledged"),
        pytest.param(True, False, id="acknowledged"),
    ],
)
async def test_stored_critical_repository_creates_an_issue_at_startup(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
    acknowledged: bool,
    has_issue: bool,
) -> None:
    """Test a removal nobody confirmed yet, like one HACS made, gets its repair."""
    hass_storage[f"{DOMAIN}.critical"] = {
        "version": STORAGE_VERSION,
        "data": [CRITICAL_REPOSITORY | {"acknowledged": acknowledged}],
    }

    await setup_integration(hass, mock_config_entry)

    assert (
        issue_registry.async_get_issue(DOMAIN, CRITICAL_ISSUE_ID) is not None
    ) is has_issue
    assert not hass.states.async_all("persistent_notification")


async def test_critical_repository_fix_flow(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    marketplace: MarketplaceManager,
) -> None:
    """Test confirming the repair acknowledges the removal."""
    assert await async_setup_component(hass, "repairs", {})
    await async_save_to_storage(
        hass, "critical", [CRITICAL_REPOSITORY | {"acknowledged": False}]
    )
    async_create_critical_repository_issue(hass, CRITICAL_REPOSITORY)

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, CRITICAL_ISSUE_ID)

    assert data["step_id"] == "confirm"
    assert data["description_placeholders"] == {
        "repository": REPOSITORY_INTEGRATION,
        "reason": CRITICAL_REPOSITORY["reason"],
    }

    data = await process_repair_fix_flow(client, data["flow_id"])

    assert data["type"] == "create_entry"
    assert issue_registry.async_get_issue(DOMAIN, CRITICAL_ISSUE_ID) is None
    assert await async_load_from_storage(hass, "critical") == [
        CRITICAL_REPOSITORY | {"acknowledged": True}
    ]


async def test_critical_repository_check_keeps_it_unacknowledged(
    hass: HomeAssistant, marketplace: MarketplaceManager
) -> None:
    """Test the next check of the catalog does not confirm a removal for the user."""
    await async_save_to_storage(
        hass, "critical", [CRITICAL_REPOSITORY | {"acknowledged": False}]
    )

    with patch.object(
        marketplace.data_client,
        "async_get_critical",
        return_value=[CRITICAL_REPOSITORY],
    ):
        await marketplace.async_handle_critical_repositories()

    assert await async_load_from_storage(hass, "critical") == [
        CRITICAL_REPOSITORY | {"acknowledged": False}
    ]


async def test_critical_repository_that_can_not_be_removed_is_tried_again(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    marketplace: MarketplaceManager,
) -> None:
    """Test a failed removal is not recorded as done, the next check retries it."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    repository.data.installed = True

    # The feed did not change, the catalog answers the second check with a 304
    with (
        patch.object(
            marketplace.data_client,
            "async_get_critical",
            side_effect=[[CRITICAL_REPOSITORY], NotModifiedError],
        ),
        patch.object(
            repository, "uninstall", side_effect=MarketplaceError("Disk is gone")
        ) as uninstall,
        patch.object(hass, "async_stop") as stop,
    ):
        await marketplace.async_handle_critical_repositories()
        await marketplace.async_handle_critical_repositories()
        await hass.async_block_till_done()

    assert uninstall.call_count == 2
    stop.assert_not_called()
    assert marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    assert issue_registry.async_get_issue(DOMAIN, CRITICAL_ISSUE_ID) is None
    assert not await async_load_from_storage(hass, "critical")


async def test_critical_repository_waits_for_its_install(
    hass: HomeAssistant, marketplace: MarketplaceManager
) -> None:
    """Test a critical repository being installed is removed once that is done."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    repository.data.installed = True
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_install(*args: Any, **kwargs: Any) -> None:
        started.set()
        await release.wait()

    with (
        patch.object(repository, "_async_install_catalog_version", slow_install),
        patch.object(repository, "_async_uninstall") as uninstall,
        patch.object(
            marketplace.data_client,
            "async_get_critical",
            return_value=[CRITICAL_REPOSITORY],
        ),
        patch.object(hass, "async_stop"),
    ):
        install = asyncio.create_task(repository.async_install_repository())
        await started.wait()

        critical = asyncio.create_task(marketplace.async_handle_critical_repositories())
        await asyncio.sleep(0)
        uninstall.assert_not_called()

        release.set()
        await install
        await critical

    uninstall.assert_called_once()
