"""Fixtures for component testing."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable, Generator
from importlib.util import find_spec
from pathlib import Path
import string
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

from aiohasupervisor.models import (
    Discovery,
    Repository,
    ResolutionInfo,
    StoreAddon,
    StoreInfo,
)
import pytest

from homeassistant.components import repairs
from homeassistant.config_entries import (
    DISCOVERY_SOURCES,
    ConfigEntriesFlowManager,
    FlowResult,
    OptionsFlowManager,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import Context, HomeAssistant, ServiceRegistry, ServiceResponse
from homeassistant.data_entry_flow import (
    FlowContext,
    FlowHandler,
    FlowManager,
    FlowResultType,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.translation import async_get_translations

if TYPE_CHECKING:
    from homeassistant.components.hassio import AddonManager

    from .conversation import MockAgent
    from .device_tracker.common import MockScanner
    from .light.common import MockLight
    from .sensor.common import MockSensor
    from .switch.common import MockSwitch


@pytest.fixture(scope="session", autouse=find_spec("zeroconf") is not None)
def patch_zeroconf_multiple_catcher() -> Generator[None]:
    """If installed, patch zeroconf wrapper that detects if multiple instances are used."""
    with patch(
        "homeassistant.components.zeroconf.install_multiple_zeroconf_catcher",
        side_effect=lambda zc: None,
    ):
        yield


@pytest.fixture(scope="session", autouse=True)
def prevent_io() -> Generator[None]:
    """Fixture to prevent certain I/O from happening."""
    with patch(
        "homeassistant.components.http.ban.load_yaml_config_file",
    ):
        yield


@pytest.fixture
def entity_registry_enabled_by_default() -> Generator[None]:
    """Test fixture that ensures all entities are enabled in the registry."""
    with patch(
        "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
        return_value=True,
    ):
        yield


# Blueprint test fixtures
@pytest.fixture(name="stub_blueprint_populate")
def stub_blueprint_populate_fixture() -> Generator[None]:
    """Stub copying the blueprints to the config folder."""
    # pylint: disable-next=import-outside-toplevel
    from .blueprint.common import stub_blueprint_populate_fixture_helper

    yield from stub_blueprint_populate_fixture_helper()


# TTS test fixtures
@pytest.fixture(name="mock_tts_get_cache_files")
def mock_tts_get_cache_files_fixture() -> Generator[MagicMock]:
    """Mock the list TTS cache function."""
    # pylint: disable-next=import-outside-toplevel
    from .tts.common import mock_tts_get_cache_files_fixture_helper

    yield from mock_tts_get_cache_files_fixture_helper()


@pytest.fixture(name="mock_tts_init_cache_dir")
def mock_tts_init_cache_dir_fixture(
    init_tts_cache_dir_side_effect: Any,
) -> Generator[MagicMock]:
    """Mock the TTS cache dir in memory."""
    # pylint: disable-next=import-outside-toplevel
    from .tts.common import mock_tts_init_cache_dir_fixture_helper

    yield from mock_tts_init_cache_dir_fixture_helper(init_tts_cache_dir_side_effect)


@pytest.fixture(name="init_tts_cache_dir_side_effect")
def init_tts_cache_dir_side_effect_fixture() -> Any:
    """Return the cache dir."""
    # pylint: disable-next=import-outside-toplevel
    from .tts.common import init_tts_cache_dir_side_effect_fixture_helper

    return init_tts_cache_dir_side_effect_fixture_helper()


@pytest.fixture(name="mock_tts_cache_dir")
def mock_tts_cache_dir_fixture(
    tmp_path: Path,
    mock_tts_init_cache_dir: MagicMock,
    mock_tts_get_cache_files: MagicMock,
    request: pytest.FixtureRequest,
) -> Generator[Path]:
    """Mock the TTS cache dir with empty dir."""
    # pylint: disable-next=import-outside-toplevel
    from .tts.common import mock_tts_cache_dir_fixture_helper

    yield from mock_tts_cache_dir_fixture_helper(
        tmp_path, mock_tts_init_cache_dir, mock_tts_get_cache_files, request
    )


@pytest.fixture(name="tts_mutagen_mock")
def tts_mutagen_mock_fixture() -> Generator[MagicMock]:
    """Mock writing tags."""
    # pylint: disable-next=import-outside-toplevel
    from .tts.common import tts_mutagen_mock_fixture_helper

    yield from tts_mutagen_mock_fixture_helper()


@pytest.fixture(name="mock_conversation_agent")
def mock_conversation_agent_fixture(hass: HomeAssistant) -> MockAgent:
    """Mock a conversation agent."""
    # pylint: disable-next=import-outside-toplevel
    from .conversation.common import mock_conversation_agent_fixture_helper

    return mock_conversation_agent_fixture_helper(hass)


@pytest.fixture(scope="session", autouse=find_spec("ffmpeg") is not None)
def prevent_ffmpeg_subprocess() -> Generator[None]:
    """If installed, prevent ffmpeg from creating a subprocess."""
    with patch(
        "homeassistant.components.ffmpeg.FFVersion.get_version", return_value="6.0"
    ):
        yield


@pytest.fixture
def mock_light_entities() -> list[MockLight]:
    """Return mocked light entities."""
    # pylint: disable-next=import-outside-toplevel
    from .light.common import MockLight

    return [
        MockLight("Ceiling", STATE_ON),
        MockLight("Ceiling", STATE_OFF),
        MockLight(None, STATE_OFF),
    ]


@pytest.fixture
def mock_sensor_entities() -> dict[str, MockSensor]:
    """Return mocked sensor entities."""
    # pylint: disable-next=import-outside-toplevel
    from .sensor.common import get_mock_sensor_entities

    return get_mock_sensor_entities()


@pytest.fixture
def mock_switch_entities() -> list[MockSwitch]:
    """Return mocked toggle entities."""
    # pylint: disable-next=import-outside-toplevel
    from .switch.common import get_mock_switch_entities

    return get_mock_switch_entities()


@pytest.fixture
def mock_legacy_device_scanner() -> MockScanner:
    """Return mocked legacy device scanner entity."""
    # pylint: disable-next=import-outside-toplevel
    from .device_tracker.common import MockScanner

    return MockScanner()


@pytest.fixture
def mock_legacy_device_tracker_setup() -> Callable[[HomeAssistant, MockScanner], None]:
    """Return setup callable for legacy device tracker setup."""
    # pylint: disable-next=import-outside-toplevel
    from .device_tracker.common import mock_legacy_device_tracker_setup

    return mock_legacy_device_tracker_setup


@pytest.fixture(name="addon_manager")
def addon_manager_fixture(
    hass: HomeAssistant, supervisor_client: AsyncMock
) -> AddonManager:
    """Return an AddonManager instance."""
    # pylint: disable-next=import-outside-toplevel
    from .hassio.common import mock_addon_manager

    return mock_addon_manager(hass)


@pytest.fixture(name="discovery_info")
def discovery_info_fixture() -> list[Discovery]:
    """Return the discovery info from the supervisor."""
    return []


@pytest.fixture(name="discovery_info_side_effect")
def discovery_info_side_effect_fixture() -> Any | None:
    """Return the discovery info from the supervisor."""
    return None


@pytest.fixture(name="get_addon_discovery_info")
def get_addon_discovery_info_fixture(
    supervisor_client: AsyncMock,
    discovery_info: list[Discovery],
    discovery_info_side_effect: Any | None,
) -> AsyncMock:
    """Mock get add-on discovery info."""
    supervisor_client.discovery.list.return_value = discovery_info
    supervisor_client.discovery.list.side_effect = discovery_info_side_effect
    return supervisor_client.discovery.list


@pytest.fixture(name="get_discovery_message_side_effect")
def get_discovery_message_side_effect_fixture() -> Any | None:
    """Side effect for getting a discovery message by uuid."""
    return None


@pytest.fixture(name="get_discovery_message")
def get_discovery_message_fixture(
    supervisor_client: AsyncMock, get_discovery_message_side_effect: Any | None
) -> AsyncMock:
    """Mock getting a discovery message by uuid."""
    supervisor_client.discovery.get.side_effect = get_discovery_message_side_effect
    return supervisor_client.discovery.get


@pytest.fixture(name="addon_store_info_side_effect")
def addon_store_info_side_effect_fixture() -> Any | None:
    """Return the add-on store info side effect."""
    return None


@pytest.fixture(name="addon_store_info")
def addon_store_info_fixture(
    supervisor_client: AsyncMock,
    addon_store_info_side_effect: Any | None,
) -> AsyncMock:
    """Mock Supervisor add-on store info."""
    # pylint: disable-next=import-outside-toplevel
    from .hassio.common import mock_addon_store_info

    return mock_addon_store_info(supervisor_client, addon_store_info_side_effect)


@pytest.fixture(name="addon_info_side_effect")
def addon_info_side_effect_fixture() -> Any | None:
    """Return the add-on info side effect."""
    return None


@pytest.fixture(name="addon_info")
def addon_info_fixture(
    supervisor_client: AsyncMock, addon_info_side_effect: Any | None
) -> AsyncMock:
    """Mock Supervisor add-on info."""
    # pylint: disable-next=import-outside-toplevel
    from .hassio.common import mock_addon_info

    return mock_addon_info(supervisor_client, addon_info_side_effect)


@pytest.fixture(name="addon_not_installed")
def addon_not_installed_fixture(
    addon_store_info: AsyncMock, addon_info: AsyncMock
) -> AsyncMock:
    """Mock add-on not installed."""
    # pylint: disable-next=import-outside-toplevel
    from .hassio.common import mock_addon_not_installed

    return mock_addon_not_installed(addon_store_info, addon_info)


@pytest.fixture(name="addon_installed")
def addon_installed_fixture(
    addon_store_info: AsyncMock, addon_info: AsyncMock
) -> AsyncMock:
    """Mock add-on already installed but not running."""
    # pylint: disable-next=import-outside-toplevel
    from .hassio.common import mock_addon_installed

    return mock_addon_installed(addon_store_info, addon_info)


@pytest.fixture(name="addon_running")
def addon_running_fixture(
    addon_store_info: AsyncMock, addon_info: AsyncMock
) -> AsyncMock:
    """Mock add-on already running."""
    # pylint: disable-next=import-outside-toplevel
    from .hassio.common import mock_addon_running

    return mock_addon_running(addon_store_info, addon_info)


@pytest.fixture(name="install_addon_side_effect")
def install_addon_side_effect_fixture(
    addon_store_info: AsyncMock, addon_info: AsyncMock
) -> Any | None:
    """Return the install add-on side effect."""

    # pylint: disable-next=import-outside-toplevel
    from .hassio.common import mock_install_addon_side_effect

    return mock_install_addon_side_effect(addon_store_info, addon_info)


@pytest.fixture(name="install_addon")
def install_addon_fixture(
    supervisor_client: AsyncMock,
    install_addon_side_effect: Any | None,
) -> AsyncMock:
    """Mock install add-on."""
    supervisor_client.store.install_addon.side_effect = install_addon_side_effect
    return supervisor_client.store.install_addon


@pytest.fixture(name="start_addon_side_effect")
def start_addon_side_effect_fixture(
    addon_store_info: AsyncMock, addon_info: AsyncMock
) -> Any | None:
    """Return the start add-on options side effect."""
    # pylint: disable-next=import-outside-toplevel
    from .hassio.common import mock_start_addon_side_effect

    return mock_start_addon_side_effect(addon_store_info, addon_info)


@pytest.fixture(name="start_addon")
def start_addon_fixture(
    supervisor_client: AsyncMock, start_addon_side_effect: Any | None
) -> AsyncMock:
    """Mock start add-on."""
    supervisor_client.addons.start_addon.side_effect = start_addon_side_effect
    return supervisor_client.addons.start_addon


@pytest.fixture(name="restart_addon_side_effect")
def restart_addon_side_effect_fixture() -> Any | None:
    """Return the restart add-on options side effect."""
    return None


@pytest.fixture(name="restart_addon")
def restart_addon_fixture(
    supervisor_client: AsyncMock,
    restart_addon_side_effect: Any | None,
) -> AsyncMock:
    """Mock restart add-on."""
    supervisor_client.addons.restart_addon.side_effect = restart_addon_side_effect
    return supervisor_client.addons.restart_addon


@pytest.fixture(name="stop_addon")
def stop_addon_fixture(supervisor_client: AsyncMock) -> AsyncMock:
    """Mock stop add-on."""
    return supervisor_client.addons.stop_addon


@pytest.fixture(name="addon_options")
def addon_options_fixture(addon_info: AsyncMock) -> dict[str, Any]:
    """Mock add-on options."""
    return addon_info.return_value.options


@pytest.fixture(name="set_addon_options_side_effect")
def set_addon_options_side_effect_fixture(
    addon_options: dict[str, Any],
) -> Any | None:
    """Return the set add-on options side effect."""
    # pylint: disable-next=import-outside-toplevel
    from .hassio.common import mock_set_addon_options_side_effect

    return mock_set_addon_options_side_effect(addon_options)


@pytest.fixture(name="set_addon_options")
def set_addon_options_fixture(
    supervisor_client: AsyncMock,
    set_addon_options_side_effect: Any | None,
) -> AsyncMock:
    """Mock set add-on options."""
    supervisor_client.addons.set_addon_options.side_effect = (
        set_addon_options_side_effect
    )
    return supervisor_client.addons.set_addon_options


@pytest.fixture(name="uninstall_addon")
def uninstall_addon_fixture(supervisor_client: AsyncMock) -> AsyncMock:
    """Mock uninstall add-on."""
    return supervisor_client.addons.uninstall_addon


@pytest.fixture(name="create_backup")
def create_backup_fixture() -> Generator[AsyncMock]:
    """Mock create backup."""
    # pylint: disable-next=import-outside-toplevel
    from .hassio.common import mock_create_backup

    yield from mock_create_backup()


@pytest.fixture(name="update_addon")
def update_addon_fixture(supervisor_client: AsyncMock) -> AsyncMock:
    """Mock update add-on."""
    return supervisor_client.store.update_addon


@pytest.fixture(name="store_addons")
def store_addons_fixture() -> list[StoreAddon]:
    """Mock store addons list."""
    return []


@pytest.fixture(name="store_repositories")
def store_repositories_fixture() -> list[Repository]:
    """Mock store repositories list."""
    return []


@pytest.fixture(name="store_info")
def store_info_fixture(
    supervisor_client: AsyncMock,
    store_addons: list[StoreAddon],
    store_repositories: list[Repository],
) -> AsyncMock:
    """Mock store info."""
    supervisor_client.store.info.return_value = StoreInfo(
        addons=store_addons, repositories=store_repositories
    )
    return supervisor_client.store.info


@pytest.fixture(name="addon_stats")
def addon_stats_fixture(supervisor_client: AsyncMock) -> AsyncMock:
    """Mock addon stats info."""
    # pylint: disable-next=import-outside-toplevel
    from .hassio.common import mock_addon_stats

    return mock_addon_stats(supervisor_client)


@pytest.fixture(name="addon_changelog")
def addon_changelog_fixture(supervisor_client: AsyncMock) -> AsyncMock:
    """Mock addon changelog."""
    supervisor_client.store.addon_changelog.return_value = ""
    return supervisor_client.store.addon_changelog


@pytest.fixture(name="supervisor_is_connected")
def supervisor_is_connected_fixture(supervisor_client: AsyncMock) -> AsyncMock:
    """Mock supervisor is connected."""
    supervisor_client.supervisor.ping.return_value = None
    return supervisor_client.supervisor.ping


@pytest.fixture(name="resolution_info")
def resolution_info_fixture(supervisor_client: AsyncMock) -> AsyncMock:
    """Mock resolution info from supervisor."""
    supervisor_client.resolution.info.return_value = ResolutionInfo(
        suggestions=[],
        unsupported=[],
        unhealthy=[],
        issues=[],
        checks=[],
    )
    return supervisor_client.resolution.info


@pytest.fixture(name="resolution_suggestions_for_issue")
def resolution_suggestions_for_issue_fixture(supervisor_client: AsyncMock) -> AsyncMock:
    """Mock suggestions by issue from supervisor resolution."""
    supervisor_client.resolution.suggestions_for_issue.return_value = []
    return supervisor_client.resolution.suggestions_for_issue


@pytest.fixture(name="supervisor_client")
def supervisor_client() -> Generator[AsyncMock]:
    """Mock the supervisor client."""
    supervisor_client = AsyncMock()
    supervisor_client.addons = AsyncMock()
    supervisor_client.discovery = AsyncMock()
    supervisor_client.homeassistant = AsyncMock()
    supervisor_client.host = AsyncMock()
    supervisor_client.os = AsyncMock()
    supervisor_client.resolution = AsyncMock()
    supervisor_client.supervisor = AsyncMock()
    with (
        patch(
            "homeassistant.components.hassio.get_supervisor_client",
            return_value=supervisor_client,
        ),
        patch(
            "homeassistant.components.hassio.handler.get_supervisor_client",
            return_value=supervisor_client,
        ),
        patch(
            "homeassistant.components.hassio.addon_manager.get_supervisor_client",
            return_value=supervisor_client,
        ),
        patch(
            "homeassistant.components.hassio.discovery.get_supervisor_client",
            return_value=supervisor_client,
        ),
        patch(
            "homeassistant.components.hassio.coordinator.get_supervisor_client",
            return_value=supervisor_client,
        ),
        patch(
            "homeassistant.components.hassio.issues.get_supervisor_client",
            return_value=supervisor_client,
        ),
        patch(
            "homeassistant.components.hassio.repairs.get_supervisor_client",
            return_value=supervisor_client,
        ),
    ):
        yield supervisor_client


def _validate_translation_placeholders(
    full_key: str,
    translation: str,
    description_placeholders: dict[str, str] | None,
    translation_errors: dict[str, str],
) -> str | None:
    """Raise if translation exists with missing placeholders."""
    tuples = list(string.Formatter().parse(translation))
    for _, placeholder, _, _ in tuples:
        if placeholder is None:
            continue
        if (
            description_placeholders is None
            or placeholder not in description_placeholders
        ):
            translation_errors[full_key] = (
                f"Description not found for placeholder `{placeholder}` in {full_key}"
            )


async def _validate_translation(
    hass: HomeAssistant,
    translation_errors: dict[str, str],
    category: str,
    component: str,
    key: str,
    description_placeholders: dict[str, str] | None,
    *,
    translation_required: bool = True,
) -> None:
    """Raise if translation doesn't exist."""
    full_key = f"component.{component}.{category}.{key}"
    translations = await async_get_translations(hass, "en", category, [component])
    if (translation := translations.get(full_key)) is not None:
        _validate_translation_placeholders(
            full_key, translation, description_placeholders, translation_errors
        )
        return

    if not translation_required:
        return

    if full_key in translation_errors:
        translation_errors[full_key] = "used"
        return

    translation_errors[full_key] = (
        f"Translation not found for {component}: `{category}.{key}`. "
        f"Please add to homeassistant/components/{component}/strings.json"
    )


@pytest.fixture
def ignore_translations() -> str | list[str]:
    """Ignore specific translations.

    Override or parametrize this fixture with a fixture that returns,
    a list of translation that should be ignored.
    """
    return []


async def _check_config_flow_result_translations(
    manager: FlowManager,
    flow: FlowHandler,
    result: FlowResult[FlowContext, str],
    translation_errors: dict[str, str],
) -> None:
    if result["type"] is FlowResultType.CREATE_ENTRY:
        # No need to check translations for a completed flow
        return

    key_prefix = ""
    if isinstance(manager, ConfigEntriesFlowManager):
        category = "config"
        integration = flow.handler
    elif isinstance(manager, OptionsFlowManager):
        category = "options"
        integration = flow.hass.config_entries.async_get_entry(flow.handler).domain
    elif isinstance(manager, repairs.RepairsFlowManager):
        category = "issues"
        integration = flow.handler
        issue_id = flow.issue_id
        issue = ir.async_get(flow.hass).async_get_issue(integration, issue_id)
        key_prefix = f"{issue.translation_key}.fix_flow."
    else:
        return

    # Check if this flow has been seen before
    # Gets set to False on first run, and to True on subsequent runs
    setattr(flow, "__flow_seen_before", hasattr(flow, "__flow_seen_before"))

    if result["type"] is FlowResultType.FORM:
        if step_id := result.get("step_id"):
            # neither title nor description are required
            # - title defaults to integration name
            # - description is optional
            for header in ("title", "description"):
                await _validate_translation(
                    flow.hass,
                    translation_errors,
                    category,
                    integration,
                    f"{key_prefix}step.{step_id}.{header}",
                    result["description_placeholders"],
                    translation_required=False,
                )
        if errors := result.get("errors"):
            for error in errors.values():
                await _validate_translation(
                    flow.hass,
                    translation_errors,
                    category,
                    integration,
                    f"{key_prefix}error.{error}",
                    result["description_placeholders"],
                )
        return

    if result["type"] is FlowResultType.ABORT:
        # We don't need translations for a discovery flow which immediately
        # aborts, since such flows won't be seen by users
        if not flow.__flow_seen_before and flow.source in DISCOVERY_SOURCES:
            return
        await _validate_translation(
            flow.hass,
            translation_errors,
            category,
            integration,
            f"{key_prefix}abort.{result["reason"]}",
            result["description_placeholders"],
        )


async def _check_create_issue_translations(
    issue_registry: ir.IssueRegistry,
    issue: ir.IssueEntry,
    translation_errors: dict[str, str],
) -> None:
    if issue.translation_key is None:
        # `translation_key` is only None on dismissed issues
        return
    await _validate_translation(
        issue_registry.hass,
        translation_errors,
        "issues",
        issue.domain,
        f"{issue.translation_key}.title",
        issue.translation_placeholders,
    )
    if not issue.is_fixable:
        # Description is required for non-fixable issues
        await _validate_translation(
            issue_registry.hass,
            translation_errors,
            "issues",
            issue.domain,
            f"{issue.translation_key}.description",
            issue.translation_placeholders,
        )


async def _check_exception_translation(
    hass: HomeAssistant,
    exception: HomeAssistantError,
    translation_errors: dict[str, str],
) -> None:
    if exception.translation_key is None:
        return
    await _validate_translation(
        hass,
        translation_errors,
        "exceptions",
        exception.translation_domain,
        f"{exception.translation_key}.message",
        exception.translation_placeholders,
    )


@pytest.fixture(autouse=True)
async def check_translations(
    ignore_translations: str | list[str],
) -> AsyncGenerator[None]:
    """Check that translation requirements are met.

    Current checks:
    - data entry flow results (ConfigFlow/OptionsFlow/RepairFlow)
    - issue registry entries
    """
    if not isinstance(ignore_translations, list):
        ignore_translations = [ignore_translations]

    translation_errors = {k: "unused" for k in ignore_translations}

    translation_coros = set()

    # Keep reference to original functions
    _original_flow_manager_async_handle_step = FlowManager._async_handle_step
    _original_issue_registry_async_create_issue = ir.IssueRegistry.async_get_or_create
    _original_service_registry_async_call = ServiceRegistry.async_call

    # Prepare override functions
    async def _flow_manager_async_handle_step(
        self: FlowManager, flow: FlowHandler, *args
    ) -> FlowResult:
        result = await _original_flow_manager_async_handle_step(self, flow, *args)
        await _check_config_flow_result_translations(
            self, flow, result, translation_errors
        )
        return result

    def _issue_registry_async_create_issue(
        self: ir.IssueRegistry, domain: str, issue_id: str, *args, **kwargs
    ) -> None:
        result = _original_issue_registry_async_create_issue(
            self, domain, issue_id, *args, **kwargs
        )
        translation_coros.add(
            _check_create_issue_translations(self, result, translation_errors)
        )
        return result

    async def _service_registry_async_call(
        self: ServiceRegistry,
        domain: str,
        service: str,
        service_data: dict[str, Any] | None = None,
        blocking: bool = False,
        context: Context | None = None,
        target: dict[str, Any] | None = None,
        return_response: bool = False,
    ) -> ServiceResponse:
        try:
            return await _original_service_registry_async_call(
                self,
                domain,
                service,
                service_data,
                blocking,
                context,
                target,
                return_response,
            )
        except HomeAssistantError as err:
            translation_coros.add(
                _check_exception_translation(self._hass, err, translation_errors)
            )
            raise

    # Use override functions
    with (
        patch(
            "homeassistant.data_entry_flow.FlowManager._async_handle_step",
            _flow_manager_async_handle_step,
        ),
        patch(
            "homeassistant.helpers.issue_registry.IssueRegistry.async_get_or_create",
            _issue_registry_async_create_issue,
        ),
        patch(
            "homeassistant.core.ServiceRegistry.async_call",
            _service_registry_async_call,
        ),
    ):
        yield

    await asyncio.gather(*translation_coros)

    # Run final checks
    unused_ignore = [k for k, v in translation_errors.items() if v == "unused"]
    if unused_ignore:
        pytest.fail(
            f"Unused ignore translations: {', '.join(unused_ignore)}. "
            "Please remove them from the ignore_translations fixture."
        )
    for description in translation_errors.values():
        if description not in {"used", "unused"}:
            pytest.fail(description)
