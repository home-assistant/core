"""Tests for the Marketplace base object."""

from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientError
import pytest
from yarl import URL

from homeassistant.components.marketplace.base import (
    MarketplaceConfiguration,
    MarketplaceManager,
    Repositories,
)
from homeassistant.components.marketplace.const import (
    CONF_WARNING_ACCEPTED,
    DOMAIN,
    WARNING_VERSION,
)
from homeassistant.components.marketplace.enums import (
    DisabledReason,
    MarketplaceSignal,
    RepositoryCategory,
)
from homeassistant.components.marketplace.exceptions import (
    ExecutionInProgressError,
    ExpectedError,
    MarketplaceError,
)
from homeassistant.components.marketplace.repositories.base import Repository
from homeassistant.core import HomeAssistant

from . import mocked_response
from .conftest import MarketplaceResponses
from .const import DEFAULT_CATEGORIES, REPOSITORY_INTEGRATION, REPOSITORY_PLUGIN

from tests.common import MockConfigEntry, MockUser
from tests.test_util.aiohttp import AiohttpClientMockResponse

DOWNLOAD_URL = "https://raw.githubusercontent.com/owner/repository/main/file.txt"
SLEEP = "homeassistant.components.marketplace.base.asyncio.sleep"


def test_configuration_reads_only_the_token() -> None:
    """Test the configuration takes the token, and nothing else, from the entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "token": "xxxxxxxxxx",
            # Options an entry of the custom integration can still carry
            "experimental": True,
            "netdaemon": True,
            "release_limit": 5,
            "plugin_path": "somewhere/else/",
            "theme_path": "somewhere/else/",
        },
    )

    configuration = MarketplaceConfiguration.from_entry(entry)

    assert configuration.config_entry is entry
    assert configuration.token == "xxxxxxxxxx"
    assert configuration.plugin_path == "www/community/"
    assert configuration.theme_path == "themes/"
    for option in ("experimental", "netdaemon", "release_limit"):
        assert not hasattr(configuration, option)


@pytest.mark.usefixtures("init_integration")
async def test_repository_lookups(
    marketplace: MarketplaceManager, mock_repository: Repository
) -> None:
    """Test looking a repository up by id and by name."""
    marketplace.repositories = Repositories()
    assert marketplace.repositories.get_by_id(None) is None
    assert marketplace.repositories.get_by_full_name(None) is None

    mock_repository.data.id = "1337"
    mock_repository.data.category = RepositoryCategory.INTEGRATION
    mock_repository.data.installed = True
    marketplace.repositories.register(mock_repository)

    assert marketplace.repositories.get_by_id("1337").data.full_name == "test/test"
    assert marketplace.repositories.get_by_full_name("test/test").data.id == "1337"
    assert marketplace.repositories.is_registered(repository_id="1337")
    assert marketplace.repositories.is_installed(repository_id="1337")
    assert not marketplace.repositories.is_installed(repository_id="404")


@pytest.mark.usefixtures("init_integration")
async def test_category_installed(
    marketplace: MarketplaceManager, mock_repository: Repository
) -> None:
    """Test only the category of an installed repository counts as installed."""
    marketplace.repositories = Repositories()
    mock_repository.data.id = "1337"
    mock_repository.data.category = RepositoryCategory.INTEGRATION
    mock_repository.data.installed = True
    marketplace.repositories.register(mock_repository)

    assert marketplace.repositories.category_installed(RepositoryCategory.INTEGRATION)
    assert not marketplace.repositories.category_installed(RepositoryCategory.THEME)


@pytest.mark.usefixtures("init_integration")
async def test_repository_id_is_set_once(
    marketplace: MarketplaceManager, mock_repository: Repository
) -> None:
    """Test a repository id can be set once and then never changes."""
    mock_repository.data.id = "0"
    marketplace.repositories.register(mock_repository)

    marketplace.repositories.set_repository_id(mock_repository, "42")

    with pytest.raises(ValueError):
        marketplace.repositories.set_repository_id(mock_repository, "30")

    # Setting the same id again is fine
    marketplace.repositories.set_repository_id(mock_repository, "42")

    assert marketplace.repositories.get_by_full_name("test/test") is mock_repository
    assert marketplace.repositories.get_by_id("42") is mock_repository


@pytest.mark.usefixtures("init_integration")
async def test_unregister_repository(
    marketplace: MarketplaceManager, mock_repository: Repository
) -> None:
    """Test unregistering a repository twice does not raise."""
    mock_repository.data.id = "42"
    marketplace.repositories.register(mock_repository)

    marketplace.repositories.unregister(mock_repository)
    assert marketplace.repositories.get_by_full_name("test/test") is None
    assert marketplace.repositories.get_by_id("42") is None

    marketplace.repositories.unregister(mock_repository)


@pytest.mark.usefixtures("init_integration")
async def test_active_categories(marketplace: MarketplaceManager) -> None:
    """Test which categories are active for the default options."""
    assert marketplace.common.categories == DEFAULT_CATEGORIES | {
        RepositoryCategory.THEME,
    }


async def test_catalog_restores_versions_of_repositories_not_installed(
    marketplace: MarketplaceManager,
) -> None:
    """Test an unchanged feed still sets the versions storage does not keep."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_PLUGIN)
    assert not repository.data.installed
    last_version = repository.data.last_version
    last_commit = repository.data.last_commit
    assert last_version or last_commit

    # Restored from storage: same fetch time as the feed, but no versions
    repository.data.last_version = None
    repository.data.last_commit = None

    await marketplace.async_get_category_repositories_from_catalog(
        RepositoryCategory.PLUGIN
    )

    assert repository.data.last_version == last_version
    assert repository.data.last_commit == last_commit


async def test_catalog_keeps_the_domain_of_an_installed_integration(
    marketplace: MarketplaceManager,
) -> None:
    """Test the feed can not point an installed integration at another directory."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    repository.data.installed = True
    repository.data.domain = "example"

    feed = {
        repository.data.id: {
            "domain": "other",
            "full_name": repository.data.full_name,
            "last_fetched": repository.data.last_fetched.timestamp() + 1,
            "manifest": {},
            "manifest_name": "Example",
        }
    }
    with patch.object(marketplace.data_client, "async_get_category", return_value=feed):
        await marketplace.async_get_category_repositories_from_catalog(
            RepositoryCategory.INTEGRATION
        )

    assert repository.data.manifest_name == "Example"
    assert repository.data.domain == "example"


async def test_custom_repository_listed_by_the_catalog_is_default(
    marketplace: MarketplaceManager,
) -> None:
    """Test a custom repository the catalog starts listing stops being custom."""
    repository = marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION)
    repository_id = str(repository.data.id)

    # Added by hand before the catalog listed it
    marketplace.repositories._default_repositories.discard(repository_id)
    assert not marketplace.repositories.is_default(repository_id)

    await marketplace.async_get_category_repositories_from_catalog(
        RepositoryCategory.INTEGRATION
    )

    assert marketplace.repositories.is_default(repository_id)
    assert (
        marketplace.repositories.get_by_full_name(REPOSITORY_INTEGRATION) is repository
    )


@pytest.mark.parametrize(
    ("reason", "runs"),
    [
        pytest.param(DisabledReason.RATE_LIMIT, True, id="rate_limit"),
        pytest.param(DisabledReason.INVALID_TOKEN, True, id="invalid_token"),
        pytest.param(DisabledReason.REMOVED, False, id="removed"),
    ],
)
async def test_catalog_work_does_not_need_github(
    marketplace: MarketplaceManager, reason: DisabledReason, runs: bool
) -> None:
    """Test the catalog is still read when only GitHub is out of reach."""
    marketplace.disable(reason)

    with (
        patch.object(
            marketplace.data_client, "async_get_category", return_value={}
        ) as get_category,
        patch.object(
            marketplace.data_client, "async_get_removed", return_value=[]
        ) as get_removed,
    ):
        await marketplace.async_get_all_category_repositories()
        await marketplace.async_handle_removed_repositories()

    assert get_category.called is runs
    assert get_removed.called is runs


async def test_removed_user_takes_the_acceptance_along(
    hass: HomeAssistant, marketplace: MarketplaceManager, hass_admin_user: MockUser
) -> None:
    """Test an automation can not install on the word of a user who is gone."""
    assert marketplace.warning_accepted(hass_admin_user.id)

    await hass.auth.async_remove_user(hass_admin_user)
    await hass.async_block_till_done()

    assert marketplace.warning_acceptances == {}
    assert marketplace.configuration.config_entry is not None
    assert marketplace.configuration.config_entry.data[CONF_WARNING_ACCEPTED] == {}


@pytest.mark.parametrize(
    "warning_accepted",
    [{"someone": {"version": WARNING_VERSION, "accepted_at": "yesterday"}}],
)
async def test_unreadable_acceptance_is_left_out(
    marketplace: MarketplaceManager,
) -> None:
    """Test an acceptance with a date that can not be read counts as none."""
    assert marketplace.warning_acceptances == {}


async def test_panel_hears_when_the_marketplace_is_disabled_or_enabled(
    marketplace: MarketplaceManager,
) -> None:
    """Test a change of the disabled reason reaches the panel, a repeat does not."""
    with patch.object(marketplace, "async_dispatch") as dispatch:
        marketplace.disable(DisabledReason.RATE_LIMIT)
        marketplace.disable(DisabledReason.RATE_LIMIT)
        marketplace.enable()
        marketplace.enable()

    assert [call.args for call in dispatch.call_args_list] == [
        (MarketplaceSignal.CONFIG, {}),
        (MarketplaceSignal.CONFIG, {}),
    ]


@pytest.mark.parametrize(
    "warning_accepted",
    [
        {
            "removed-while-unloaded": {
                "version": WARNING_VERSION,
                "accepted_at": "2026-09-01T12:00:00+00:00",
            }
        }
    ],
)
async def test_acceptance_of_a_user_removed_while_unloaded_is_forgotten(
    marketplace: MarketplaceManager,
) -> None:
    """Test a user removed while the Marketplace was not loaded counts for nothing."""
    assert marketplace.warning_acceptances == {}
    assert marketplace.configuration.config_entry is not None
    assert marketplace.configuration.config_entry.data[CONF_WARNING_ACCEPTED] == {}


@pytest.mark.parametrize(
    ("can_update", "tasks_run"),
    [
        pytest.param(1, 2, id="one_at_a_time"),
        pytest.param(0, 0, id="rate_limited"),
    ],
)
async def test_process_queue(
    marketplace: MarketplaceManager, can_update: int, tasks_run: int
) -> None:
    """Test the queue runs what the rate limit allows and stores the outcome."""
    ran: list[int] = []

    async def task(number: int) -> None:
        ran.append(number)

    marketplace.queue.add(task(1))
    marketplace.queue.add(task(2))

    with (
        patch.object(marketplace, "async_can_update", return_value=can_update),
        patch.object(marketplace.data, "async_write") as write,
    ):
        await marketplace.async_process_queue()

    assert len(ran) == tasks_run
    assert write.called is bool(tasks_run)
    marketplace.queue.clear()


def _rate_limit(remaining: int) -> MagicMock:
    """Return what GitHub answers about the rate limit."""
    response = MagicMock()
    response.data.resources.core.remaining = remaining
    response.data.resources.core.reset = 0
    return response


@pytest.mark.parametrize(
    ("remaining", "can_update", "reason"),
    [
        pytest.param(5000, 400, None, id="room_left"),
        pytest.param(1005, 0, DisabledReason.RATE_LIMIT, id="nearly_out"),
    ],
)
async def test_rate_limit_decides_how_much_can_update(
    marketplace: MarketplaceManager,
    remaining: int,
    can_update: int,
    reason: DisabledReason | None,
) -> None:
    """Test the rate limit keeps 1000 requests aside, and stops work below that."""
    with patch.object(
        marketplace,
        "async_github_api_method",
        AsyncMock(return_value=_rate_limit(remaining)),
    ):
        assert await marketplace.async_can_update() == can_update

    assert marketplace.system.disabled_reason == reason


async def test_rate_limit_that_can_not_be_read_updates_nothing(
    marketplace: MarketplaceManager,
) -> None:
    """Test an unknown rate limit is treated as none left."""
    with patch.object(
        marketplace,
        "async_github_api_method",
        AsyncMock(side_effect=MarketplaceError("no route to host")),
    ):
        assert await marketplace.async_can_update() == 0

    assert not marketplace.system.disabled


@pytest.mark.parametrize(
    ("can_update", "enabled"),
    [
        pytest.param(10, True, id="lifted"),
        pytest.param(0, False, id="still_limited"),
    ],
)
async def test_rate_limit_check_starts_again_once_it_lifted(
    marketplace: MarketplaceManager, can_update: int, enabled: bool
) -> None:
    """Test the Marketplace carries on with its queue once the limit lifted."""
    marketplace.disable(DisabledReason.RATE_LIMIT)

    with (
        patch.object(marketplace, "async_can_update", return_value=can_update),
        patch.object(marketplace, "async_process_queue") as process_queue,
    ):
        await marketplace.async_check_rate_limit()

    assert marketplace.system.disabled is not enabled
    assert process_queue.called is enabled


async def test_rate_limit_check_leaves_other_reasons_alone(
    marketplace: MarketplaceManager,
) -> None:
    """Test only a rate limit is checked for lifting, other reasons stay."""
    marketplace.disable(DisabledReason.REMOVED)

    with patch.object(marketplace, "async_can_update") as can_update:
        await marketplace.async_check_rate_limit()

    can_update.assert_not_called()
    assert marketplace.system.disabled_reason == DisabledReason.REMOVED


async def test_queue_waits_while_disabled_empty_or_running(
    marketplace: MarketplaceManager,
) -> None:
    """Test the queue only runs when there is something to run, and room for it."""

    async def task() -> None:
        """Do nothing, the queue only has to hold it."""

    with patch.object(marketplace.queue, "execute") as execute:
        # Nothing in it
        await marketplace.async_process_queue()

        marketplace.queue.add(task())
        marketplace.disable(DisabledReason.RATE_LIMIT)
        await marketplace.async_process_queue()

        marketplace.enable()
        marketplace.queue.running = True
        await marketplace.async_process_queue()

    execute.assert_not_called()
    marketplace.queue.running = False
    marketplace.queue.clear()


async def test_queue_stops_when_another_run_took_over(
    marketplace: MarketplaceManager,
) -> None:
    """Test a run that finds the queue taken leaves it to that one."""

    async def task() -> None:
        """Do nothing, the queue only has to hold it."""

    marketplace.queue.add(task())
    with (
        patch.object(marketplace, "async_can_update", return_value=10),
        patch.object(
            marketplace.queue, "execute", side_effect=ExecutionInProgressError
        ),
        patch.object(marketplace.data, "async_write") as write,
    ):
        await marketplace.async_process_queue()

    write.assert_not_called()
    marketplace.queue.clear()


@pytest.mark.parametrize("github_token", [None])
async def test_queue_waits_for_a_github_connection(
    marketplace: MarketplaceManager,
) -> None:
    """Test the queue does not spend the small anonymous rate limit."""

    async def task() -> None:
        """Do nothing, the queue only has to hold it."""

    marketplace.queue.add(task())
    with patch.object(marketplace.queue, "execute") as execute:
        await marketplace.async_process_queue()

    execute.assert_not_called()
    marketplace.queue.clear()


async def test_download_gives_up_after_five_timeouts(
    marketplace: MarketplaceManager, response_mocker: MarketplaceResponses
) -> None:
    """Test a download that keeps timing out stops trying."""
    response_mocker.add(
        DOWNLOAD_URL,
        AiohttpClientMockResponse("get", URL(DOWNLOAD_URL), exc=TimeoutError),
        keep=True,
    )

    with patch(SLEEP) as sleep:
        assert await marketplace.async_download_file(DOWNLOAD_URL) is None

    assert sleep.call_count == 5


@pytest.mark.parametrize(
    ("retry_after", "waited"),
    [
        pytest.param("2", 2, id="as_asked"),
        pytest.param("soon", 10, id="unreadable"),
        pytest.param("600", 60, id="capped"),
    ],
)
async def test_download_waits_out_a_rate_limit(
    marketplace: MarketplaceManager,
    response_mocker: MarketplaceResponses,
    retry_after: str,
    waited: int,
) -> None:
    """Test a rate limited download waits what GitHub asks, within reason."""
    response_mocker.add(
        DOWNLOAD_URL,
        mocked_response(
            DOWNLOAD_URL,
            status=HTTPStatus.TOO_MANY_REQUESTS,
            headers={"retry-after": retry_after},
        ),
    )
    waits: list[int] = []

    async def wait(seconds: int) -> None:
        # By the time the wait is over, GitHub answers
        waits.append(seconds)
        response_mocker.add(DOWNLOAD_URL, mocked_response(DOWNLOAD_URL, content=b"ok"))

    with patch(SLEEP, wait):
        content = await marketplace.async_download_file(
            DOWNLOAD_URL, handle_rate_limit=True
        )

    assert content == b"ok"
    assert waits == [waited]


@pytest.mark.parametrize(
    "response",
    [
        pytest.param(
            mocked_response(DOWNLOAD_URL, status=HTTPStatus.NOT_FOUND), id="status"
        ),
        pytest.param(
            AiohttpClientMockResponse("get", URL(DOWNLOAD_URL), exc=ClientError),
            id="exception",
        ),
    ],
)
async def test_download_that_fails_gives_nothing(
    marketplace: MarketplaceManager,
    response_mocker: MarketplaceResponses,
    response: AiohttpClientMockResponse,
) -> None:
    """Test a download that fails for another reason is not tried again."""
    response_mocker.add(DOWNLOAD_URL, response)

    with patch(SLEEP) as sleep:
        assert await marketplace.async_download_file(DOWNLOAD_URL) is None

    sleep.assert_not_called()


async def test_register_skips_what_it_was_told_to(
    marketplace: MarketplaceManager,
) -> None:
    """Test a repository on the skip list is not registered."""
    marketplace.common.skip.add("owner/skipped")

    with pytest.raises(ExpectedError):
        await marketplace.async_register_repository(
            "owner/skipped", RepositoryCategory.INTEGRATION
        )


async def test_register_refuses_an_unknown_category(
    marketplace: MarketplaceManager,
) -> None:
    """Test a category the Marketplace does not have registers nothing."""
    assert (
        await marketplace.async_register_repository("owner/unknown", "python_script")
        is None
    )
    assert marketplace.repositories.get_by_full_name("owner/unknown") is None
