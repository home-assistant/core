"""Fixtures for component testing."""

import asyncio
from collections.abc import AsyncGenerator, Callable, Coroutine, Generator, Mapping
from functools import lru_cache
from importlib.util import find_spec
import inspect
from pathlib import Path
import re
import string
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import probatio
import pytest
from pytest_homeassistant.common import QualityScaleStatus, get_quality_scale

from homeassistant import components, loader
from homeassistant.components import repairs
from homeassistant.config_entries import (
    DISCOVERY_SOURCES,
    ConfigEntriesFlowManager,
    ConfigSubentryFlowManager,
    FlowResult,
    OptionsFlowManager,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import (
    Context,
    EntityServiceResponse,
    HassJobType,
    HomeAssistant,
    ServiceCall,
    ServiceRegistry,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.data_entry_flow import (
    FlowContext,
    FlowHandler,
    FlowManager,
    FlowResultType,
    section,
)
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.translation import async_get_translations
from homeassistant.helpers.typing import VolSchemaType
from homeassistant.util import yaml as yaml_util

if TYPE_CHECKING:
    from .conversation import MockAgent
    from .device_tracker.common import MockScanner
    from .light.common import MockLight
    from .sensor.common import MockSensor
    from .switch.common import MockSwitch

pytest.register_assert_rewrite("pytest_homeassistant.components.common")

# Regex for accessing the integration name from the test path
RE_REQUEST_DOMAIN = re.compile(r".*tests\/components\/([^/]+)\/.*")


@pytest.fixture(scope="session", autouse=find_spec("zeroconf") is not None)
def patch_zeroconf_multiple_catcher() -> Generator[None]:
    """Patch zeroconf wrapper that detects multiple instances."""
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


# TTS test fixtures
@pytest.fixture(name="mock_tts_get_cache_files")
def mock_tts_get_cache_files_fixture() -> Generator[MagicMock]:
    """Mock the list TTS cache function."""
    from .tts.common import mock_tts_get_cache_files_fixture_helper  # noqa: PLC0415

    yield from mock_tts_get_cache_files_fixture_helper()


@pytest.fixture(name="mock_tts_init_cache_dir")
def mock_tts_init_cache_dir_fixture(
    init_tts_cache_dir_side_effect: Any,
) -> Generator[MagicMock]:
    """Mock the TTS cache dir in memory."""
    from .tts.common import mock_tts_init_cache_dir_fixture_helper  # noqa: PLC0415

    yield from mock_tts_init_cache_dir_fixture_helper(init_tts_cache_dir_side_effect)


@pytest.fixture(name="init_tts_cache_dir_side_effect")
def init_tts_cache_dir_side_effect_fixture() -> Any:
    """Return the cache dir."""
    from .tts.common import (  # noqa: PLC0415
        init_tts_cache_dir_side_effect_fixture_helper,
    )

    return init_tts_cache_dir_side_effect_fixture_helper()


@pytest.fixture(name="mock_tts_cache_dir")
def mock_tts_cache_dir_fixture(
    tmp_path: Path,
    mock_tts_init_cache_dir: MagicMock,
    mock_tts_get_cache_files: MagicMock,
    request: pytest.FixtureRequest,
) -> Generator[Path]:
    """Mock the TTS cache dir with empty dir."""
    from .tts.common import mock_tts_cache_dir_fixture_helper  # noqa: PLC0415

    yield from mock_tts_cache_dir_fixture_helper(
        tmp_path, mock_tts_init_cache_dir, mock_tts_get_cache_files, request
    )


@pytest.fixture(name="tts_mutagen_mock")
def tts_mutagen_mock_fixture() -> Generator[MagicMock]:
    """Mock writing tags."""
    from .tts.common import tts_mutagen_mock_fixture_helper  # noqa: PLC0415

    yield from tts_mutagen_mock_fixture_helper()


@pytest.fixture(name="mock_conversation_agent")
def mock_conversation_agent_fixture(hass: HomeAssistant) -> MockAgent:
    """Mock a conversation agent."""
    from .conversation.common import (  # noqa: PLC0415
        mock_conversation_agent_fixture_helper,
    )

    return mock_conversation_agent_fixture_helper(hass)


@pytest.fixture(scope="session", autouse=find_spec("haffmpeg") is not None)
def prevent_ffmpeg_subprocess() -> Generator[None]:
    """If installed, prevent ffmpeg from creating a subprocess."""
    with patch(
        "homeassistant.components.ffmpeg.FFVersion.get_version", return_value="6.0"
    ):
        yield


@pytest.fixture
def mock_light_entities() -> list[MockLight]:
    """Return mocked light entities."""
    from .light.common import MockLight  # noqa: PLC0415

    return [
        MockLight("Ceiling", STATE_ON),
        MockLight("Ceiling", STATE_OFF),
        MockLight(None, STATE_OFF),
    ]


@pytest.fixture
def mock_sensor_entities() -> dict[str, MockSensor]:
    """Return mocked sensor entities."""
    from .sensor.common import get_mock_sensor_entities  # noqa: PLC0415

    return get_mock_sensor_entities()


@pytest.fixture
def mock_switch_entities() -> list[MockSwitch]:
    """Return mocked toggle entities."""
    from .switch.common import get_mock_switch_entities  # noqa: PLC0415

    return get_mock_switch_entities()


@pytest.fixture
def mock_legacy_device_scanner() -> MockScanner:
    """Return mocked legacy device scanner entity."""
    from .device_tracker.common import MockScanner  # noqa: PLC0415

    return MockScanner()


@pytest.fixture
def mock_legacy_device_tracker_setup() -> Callable[[HomeAssistant, MockScanner], None]:
    """Return setup callable for legacy device tracker setup."""
    from .device_tracker.common import mock_legacy_device_tracker_setup  # noqa: PLC0415

    return mock_legacy_device_tracker_setup


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
    ignore_translations_for_mock_domains: set[str],
    category: str,
    component: str,
    key: str,
    description_placeholders: Mapping[str, str] | None,
    *,
    translation_required: bool = True,
) -> None:
    """Raise if translation doesn't exist."""
    full_key = f"component.{component}.{category}.{key}"
    if component in ignore_translations_for_mock_domains:
        try:
            integration = await loader.async_get_integration(hass, component)
        except loader.IntegrationNotFound:
            return
        component_paths = components.__path__
        if not any(
            Path(f"{component_path}/{component}") == integration.file_path
            for component_path in component_paths
        ):
            return
        # If the integration exists, translation errors should be ignored via the
        # ignore_missing_translations fixture instead of the
        # ignore_translations_for_mock_domains fixture.
        translation_errors[full_key] = f"The integration '{component}' exists"
        return

    translations = await async_get_translations(hass, "en", category, [component])

    if full_key.endswith("."):
        for subkey, translation in translations.items():
            if subkey.startswith(full_key):
                _validate_translation_placeholders(
                    subkey, translation, description_placeholders, translation_errors
                )
        return
    if (translation := translations.get(full_key)) is not None:
        _validate_translation_placeholders(
            full_key, translation, description_placeholders, translation_errors
        )
        return

    if not translation_required:
        return

    if full_key not in translation_errors:
        for k in translation_errors:
            if k.endswith(".") and full_key.startswith(k):
                full_key = k
                break
    if translation_errors.get(full_key) in {"used", "unused"}:
        # If the integration does not exist, translation errors should be ignored
        # via the ignore_translations_for_mock_domains fixture instead of the
        # ignore_missing_translations fixture.
        try:
            await loader.async_get_integration(hass, component)
        except loader.IntegrationNotFound:
            translation_errors[full_key] = (
                f"Translation not found for {component}: `{category}.{key}`. "
                f"The integration '{component}' does not exist."
            )
            return

        # This translation key is in the ignore list, mark it as used
        translation_errors[full_key] = "used"
        return

    translation_errors[full_key] = (
        f"Translation not found for {component}: `{category}.{key}`. "
        f"Please add to homeassistant/components/{component}/strings.json"
    )


async def _validate_abort_translation_not_duplicated(
    hass: HomeAssistant,
    translation_errors: dict[str, str],
    ignore_translations_for_mock_domains: set[str],
    category: str,
    component: str,
    translation_domain: str,
    key: str,
    *,
    shared_category: str | None = None,
    shared_key: str | None = None,
) -> None:
    """Raise if an integration duplicates an abort translated by another domain.

    A local translation with different wording is kept, since the integration
    may raise the same reason itself to show its own wording.
    """
    if component in ignore_translations_for_mock_domains:
        return
    full_key = f"component.{component}.{category}.{key}"
    translations = await async_get_translations(hass, "en", category, [component])
    if (translation := translations.get(full_key)) is None:
        return
    shared_category = shared_category or category
    shared_translations = await async_get_translations(
        hass, "en", shared_category, [translation_domain]
    )
    if translation == shared_translations.get(
        f"component.{translation_domain}.{shared_category}.{shared_key or key}"
    ):
        translation_errors[full_key] = (
            f"Translation `{category}.{key}` of {component} duplicates the one of "
            f"{translation_domain}, which translates this abort. Please remove it "
            f"from homeassistant/components/{component}/strings.json and pass "
            f'translation_domain="{translation_domain}" wherever {component} '
            "raises this reason itself"
        )


@pytest.fixture
def ignore_missing_translations() -> str | list[str]:
    """Ignore specific missing translations.

    Override or parametrize this fixture with a fixture that returns
    a list of missing translation that should be ignored.
    """
    return []


@pytest.fixture
def ignore_translations_for_mock_domains() -> str | list[str]:
    """Don't validate translations for specific domains.

    Override or parametrize this fixture with a fixture that returns
    a list of domains for which translations should not be validated.
    This should only be used when testing mocked integrations.
    """
    return []


@lru_cache
def _get_integration_quality_scale(integration: str) -> dict[str, Any]:
    """Get the quality scale for an integration."""
    try:
        return yaml_util.load_yaml_dict(
            f"homeassistant/components/{integration}/quality_scale.yaml"
        ).get("rules", {})
    except FileNotFoundError:
        return {}


def _get_integration_quality_scale_rule(integration: str, rule: str) -> str:
    """Get the quality scale for an integration."""
    quality_scale = _get_integration_quality_scale(integration)
    if not quality_scale or rule not in quality_scale:
        return "todo"
    status = quality_scale[rule]
    return status if isinstance(status, str) else status["status"]


async def _check_step_or_section_translations(
    hass: HomeAssistant,
    translation_errors: dict[str, str],
    category: str,
    integration: str,
    translation_prefix: str,
    description_placeholders: dict[str, str],
    data_schema: probatio.Schema | None,
    ignore_translations_for_mock_domains: set[str],
) -> None:
    # neither title nor description are required
    # - title defaults to integration name
    # - description is optional
    for header in ("title", "description"):
        await _validate_translation(
            hass,
            translation_errors,
            ignore_translations_for_mock_domains,
            category,
            integration,
            f"{translation_prefix}.{header}",
            description_placeholders,
            translation_required=False,
        )

    if not data_schema:
        return

    for data_key, data_value in data_schema.schema.items():
        if isinstance(data_value, section):
            # check the nested section
            await _check_step_or_section_translations(
                hass,
                translation_errors,
                category,
                integration,
                f"{translation_prefix}.sections.{data_key}",
                description_placeholders,
                data_value.schema,
                ignore_translations_for_mock_domains,
            )
            continue
        iqs_config_flow = _get_integration_quality_scale_rule(
            integration, "config-flow"
        )
        # data and data_description are compulsory
        for header in ("data", "data_description"):
            await _validate_translation(
                hass,
                translation_errors,
                ignore_translations_for_mock_domains,
                category,
                integration,
                f"{translation_prefix}.{header}.{data_key}",
                description_placeholders,
                translation_required=(iqs_config_flow == "done"),
            )


async def _check_config_flow_result_translations(
    manager: FlowManager,
    flow: FlowHandler,
    result: FlowResult[FlowContext, str],
    translation_errors: dict[str, str],
    ignore_translations_for_mock_domains: set[str],
) -> None:
    if result["type"] is FlowResultType.CREATE_ENTRY:
        # No need to check translations for a completed flow
        return

    key_prefix = ""
    description_placeholders = result.get("description_placeholders")
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
        if issue is None:
            # Issue was deleted mid-flow (e.g., config entry removed), skip check
            return
        key_prefix = f"{issue.translation_key}.fix_flow."
        description_placeholders = {
            # Both are used in issue translations, and description_placeholders
            # takes precedence over translation_placeholders
            **(issue.translation_placeholders or {}),
            **(description_placeholders or {}),
        }
    elif isinstance(manager, ConfigSubentryFlowManager):
        # Subentry flows are only checked for duplicated shared abort translations
        if (
            result["type"] is FlowResultType.ABORT
            and (abort_domain := result.get("translation_domain")) is not None
            and (entry := flow.hass.config_entries.async_get_entry(flow.handler[0]))
            and abort_domain != entry.domain
        ):
            # The frontend resolves a shared subentry abort from the config section
            await _validate_abort_translation_not_duplicated(
                flow.hass,
                translation_errors,
                ignore_translations_for_mock_domains,
                "config_subentries",
                entry.domain,
                abort_domain,
                f"{flow.handler[1]}.abort.{result['reason']}",
                shared_category="config",
                shared_key=f"abort.{result['reason']}",
            )
        return
    else:
        return

    # Check if this flow has been seen before
    # Gets set to False on first run, and to True on subsequent runs
    setattr(flow, "__flow_seen_before", hasattr(flow, "__flow_seen_before"))

    if result["type"] is FlowResultType.FORM:
        if step_id := result.get("step_id"):
            await _check_step_or_section_translations(
                flow.hass,
                translation_errors,
                category,
                integration,
                f"{key_prefix}step.{step_id}",
                description_placeholders,
                result["data_schema"],
                ignore_translations_for_mock_domains,
            )

        if errors := result.get("errors"):
            for error in errors.values():
                await _validate_translation(
                    flow.hass,
                    translation_errors,
                    ignore_translations_for_mock_domains,
                    category,
                    integration,
                    f"{key_prefix}error.{error}",
                    description_placeholders,
                )
        return

    if result["type"] is FlowResultType.ABORT:
        abort_domain = result.get("translation_domain")
        if abort_domain is not None and abort_domain != integration:
            await _validate_abort_translation_not_duplicated(
                flow.hass,
                translation_errors,
                ignore_translations_for_mock_domains,
                category,
                integration,
                abort_domain,
                f"{key_prefix}abort.{result['reason']}",
            )
        # We don't need translations for a discovery flow which immediately
        # aborts, since such flows won't be seen by users
        if not flow.__flow_seen_before and flow.source in DISCOVERY_SOURCES:
            return
        if abort_domain is not None:
            integration = abort_domain
        await _validate_translation(
            flow.hass,
            translation_errors,
            ignore_translations_for_mock_domains,
            category,
            integration,
            f"{key_prefix}abort.{result['reason']}",
            description_placeholders,
        )


async def _check_create_issue_translations(
    issue_registry: ir.IssueRegistry,
    issue: ir.IssueEntry,
    translation_errors: dict[str, str],
    ignore_translations_for_mock_domains: set[str],
) -> None:
    if issue.translation_key is None:
        # `translation_key` is only None on dismissed issues
        return
    await _validate_translation(
        issue_registry.hass,
        translation_errors,
        ignore_translations_for_mock_domains,
        "issues",
        issue.domain,
        f"{issue.translation_key}.title",
        issue.translation_placeholders,
    )
    if (
        not issue.is_fixable
        and issue.translation_key
        not in ir.FRONTEND_HANDLED_ISSUES.get(issue.domain, ())
    ):
        # Description is required for non-fixable issues
        await _validate_translation(
            issue_registry.hass,
            translation_errors,
            ignore_translations_for_mock_domains,
            "issues",
            issue.domain,
            f"{issue.translation_key}.description",
            issue.translation_placeholders,
        )


def _get_request_quality_scale(
    request: pytest.FixtureRequest, rule: str
) -> QualityScaleStatus:
    if not (match := RE_REQUEST_DOMAIN.match(str(request.path))):
        return QualityScaleStatus.TODO
    integration = match.groups(1)[0]
    return get_quality_scale(integration).get(rule, QualityScaleStatus.TODO)


async def _check_exception_translation(
    hass: HomeAssistant,
    exception: HomeAssistantError,
    translation_errors: dict[str, str],
    request: pytest.FixtureRequest,
    ignore_translations_for_mock_domains: set[str],
) -> None:
    if isinstance(exception, Unauthorized):
        return
    if exception.translation_key is None:
        if (
            _get_request_quality_scale(request, "exception-translations")
            is QualityScaleStatus.DONE
        ):
            translation_errors["quality_scale"] = (
                f"Found untranslated {type(exception).__name__} exception: {exception}"
            )
        return
    await _validate_translation(
        hass,
        translation_errors,
        ignore_translations_for_mock_domains,
        "exceptions",
        exception.translation_domain,
        f"{exception.translation_key}.message",
        exception.translation_placeholders,
    )


_DYNAMIC_SERVICE_DOMAINS = {
    "esphome",
    "notify",
    "rest_command",
    "script",
    "shell_command",
    "tts",
}
"""These domains create services dynamically.

name/description translations are not required.
"""


async def _check_service_registration_translation(
    hass: HomeAssistant,
    domain: str,
    service_name: str,
    description_placeholders: Mapping[str, str] | None,
    translation_errors: dict[str, str],
    ignore_translations_for_mock_domains: set[str],
) -> None:
    # Use trailing . to check all subkeys
    # This validates placeholders only, and only if the translation exists
    await _validate_translation(
        hass,
        translation_errors,
        ignore_translations_for_mock_domains,
        "services",
        domain,
        f"{service_name}.",
        description_placeholders,
    )
    # Service `name` and `description` should be compulsory
    # unless for specific domains where the services are dynamically created
    if domain not in _DYNAMIC_SERVICE_DOMAINS:
        for subkey in ("name", "description"):
            await _validate_translation(
                hass,
                translation_errors,
                ignore_translations_for_mock_domains,
                "services",
                domain,
                f"{service_name}.{subkey}",
                description_placeholders,
                translation_required=True,
            )


@pytest.fixture(autouse=True)
async def check_translations(
    ignore_missing_translations: str | list[str],
    ignore_translations_for_mock_domains: str | list[str],
    request: pytest.FixtureRequest,
) -> AsyncGenerator[None]:
    """Check that translation requirements are met.

    Current checks:
    - data entry flow results (ConfigFlow/OptionsFlow/RepairFlow)
    - data entry flow aborts translated by another domain are not duplicated locally
      (also for ConfigSubentryFlow)
    - issue registry entries
    - action (service) exceptions
    """
    if not isinstance(ignore_missing_translations, list):
        ignore_missing_translations = [ignore_missing_translations]

    if not isinstance(ignore_translations_for_mock_domains, list):
        ignored_domains = {ignore_translations_for_mock_domains}
    else:
        ignored_domains = set(ignore_translations_for_mock_domains)

    # Set all ignored translation keys to "unused"
    translation_errors = dict.fromkeys(ignore_missing_translations, "unused")

    translation_coros = set()

    # Keep reference to original functions
    _original_flow_manager_async_handle_step = FlowManager._async_handle_step
    _original_issue_registry_async_create_issue = ir.IssueRegistry.async_get_or_create
    _original_service_registry_async_call = ServiceRegistry.async_call
    _original_service_registry_async_register = ServiceRegistry.async_register

    # Prepare override functions
    async def _flow_manager_async_handle_step(
        self: FlowManager, flow: FlowHandler, *args
    ) -> FlowResult:
        result = await _original_flow_manager_async_handle_step(self, flow, *args)
        await _check_config_flow_result_translations(
            self, flow, result, translation_errors, ignored_domains
        )
        return result

    def _issue_registry_async_create_issue(
        self: ir.IssueRegistry, domain: str, issue_id: str, *args, **kwargs
    ) -> ir.IssueEntry:
        result = _original_issue_registry_async_create_issue(
            self, domain, issue_id, *args, **kwargs
        )
        translation_coros.add(
            _check_create_issue_translations(
                self, result, translation_errors, ignored_domains
            )
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
                _check_exception_translation(
                    self._hass,
                    err,
                    translation_errors,
                    request,
                    ignored_domains,
                )
            )
            raise

    @callback
    def _service_registry_async_register(
        self: ServiceRegistry,
        domain: str,
        service: str,
        service_func: Callable[
            [ServiceCall],
            Coroutine[Any, Any, ServiceResponse | EntityServiceResponse]
            | ServiceResponse
            | EntityServiceResponse
            | None,
        ],
        schema: VolSchemaType | None = None,
        supports_response: SupportsResponse = SupportsResponse.NONE,
        job_type: HassJobType | None = None,
        *,
        description_placeholders: Mapping[str, str] | None = None,
    ) -> None:
        if (
            (current_frame := inspect.currentframe()) is None
            or (caller := current_frame.f_back) is None
            or (
                # async_mock_service is used in tests to register test services
                caller.f_code.co_name != "async_mock_service"
                # ServiceRegistry.async_register can also be called directly in
                # a test module
                and not caller.f_code.co_filename.startswith(
                    str(Path(__file__).parents[0])
                )
            )
        ):
            translation_coros.add(
                _check_service_registration_translation(
                    self._hass,
                    domain,
                    service,
                    description_placeholders,
                    translation_errors,
                    ignored_domains,
                )
            )

        _original_service_registry_async_register(
            self,
            domain,
            service,
            service_func,
            schema,
            supports_response,
            job_type,
            description_placeholders=description_placeholders,
        )

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
        patch(
            "homeassistant.core.ServiceRegistry.async_register",
            _service_registry_async_register,
        ),
    ):
        yield

    await asyncio.gather(*translation_coros)

    # Run final checks
    unused_ignore = [k for k, v in translation_errors.items() if v == "unused"]
    if unused_ignore:
        # Some ignored translations were not used
        pytest.fail(
            f"Unused ignore translations: {', '.join(unused_ignore)}. "
            "Please remove them from the ignore_missing_translations fixture."
        )
    for description in translation_errors.values():
        if description != "used":
            pytest.fail(description)
