"""Fixtures for component testing."""

from __future__ import annotations

from collections.abc import Callable, Generator
from importlib.util import find_spec
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

from aiohasupervisor.models import Repository, StoreAddon, StoreInfo
import pytest

from homeassistant.config_entries import (
    DISCOVERY_SOURCES,
    ConfigEntriesFlowManager,
    FlowResult,
    OptionsFlowManager,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowHandler, FlowManager, FlowResultType
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
def discovery_info_fixture() -> Any:
    """Return the discovery info from the supervisor."""
    # pylint: disable-next=import-outside-toplevel
    from .hassio.common import mock_discovery_info

    return mock_discovery_info()


@pytest.fixture(name="discovery_info_side_effect")
def discovery_info_side_effect_fixture() -> Any | None:
    """Return the discovery info from the supervisor."""
    return None


@pytest.fixture(name="get_addon_discovery_info")
def get_addon_discovery_info_fixture(
    discovery_info: dict[str, Any], discovery_info_side_effect: Any | None
) -> Generator[AsyncMock]:
    """Mock get add-on discovery info."""
    # pylint: disable-next=import-outside-toplevel
    from .hassio.common import mock_get_addon_discovery_info

    yield from mock_get_addon_discovery_info(discovery_info, discovery_info_side_effect)


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
    supervisor_client.addons.addon_options.side_effect = set_addon_options_side_effect
    return supervisor_client.addons.addon_options


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


@pytest.fixture(name="supervisor_client")
def supervisor_client() -> Generator[AsyncMock]:
    """Mock the supervisor client."""
    supervisor_client = AsyncMock()
    supervisor_client.addons = AsyncMock()
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
            "homeassistant.components.hassio.get_supervisor_client",
            return_value=supervisor_client,
        ),
    ):
        yield supervisor_client


async def _ensure_translation_exists(
    hass: HomeAssistant,
    ignore_translations: dict[str, StoreInfo],
    category: str,
    component: str,
    key: str,
) -> None:
    """Raise if translation doesn't exist."""
    full_key = f"component.{component}.{category}.{key}"
    translations = await async_get_translations(hass, "en", category, [component])
    if full_key in translations:
        return

    if full_key in ignore_translations:
        ignore_translations[full_key] = "used"
        return

    key_parts = key.split(".")
    # Ignore step data translations if title or description exists
    if (
        len(key_parts) >= 3
        and key_parts[0] == "step"
        and key_parts[2] == "data"
        and (
            f"component.{component}.{category}.{key_parts[0]}.{key_parts[1]}.description"
            in translations
            or f"component.{component}.{category}.{key_parts[0]}.{key_parts[1]}.title"
            in translations
        )
    ):
        return

    pytest.fail(
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


@pytest.fixture(autouse=True)
def check_config_translations(ignore_translations: str | list[str]) -> Generator[None]:
    """Ensure config_flow translations are available."""
    if not isinstance(ignore_translations, list):
        ignore_translations = [ignore_translations]

    _ignore_translations = {k: "unused" for k in ignore_translations}
    _original = FlowManager._async_handle_step

    async def _async_handle_step(
        self: FlowManager, flow: FlowHandler, *args
    ) -> FlowResult:
        result = await _original(self, flow, *args)
        if isinstance(self, ConfigEntriesFlowManager):
            category = "config"
            component = flow.handler
        elif isinstance(self, OptionsFlowManager):
            category = "options"
            component = flow.hass.config_entries.async_get_entry(flow.handler).domain
        else:
            return result

        # Check if this flow has been seen before
        # Gets set to False on first run, and to True on subsequent runs
        setattr(flow, "__flow_seen_before", hasattr(flow, "__flow_seen_before"))

        if result["type"] is FlowResultType.FORM:
            if errors := result.get("errors"):
                for error in errors.values():
                    await _ensure_translation_exists(
                        flow.hass,
                        _ignore_translations,
                        category,
                        component,
                        f"error.{error}",
                    )
            return result

        if result["type"] is FlowResultType.ABORT:
            # We don't need translations for a discovery flow which immediately
            # aborts, since such flows won't be seen by users
            if not flow.__flow_seen_before and flow.source in DISCOVERY_SOURCES:
                return result
            await _ensure_translation_exists(
                flow.hass,
                _ignore_translations,
                category,
                component,
                f"abort.{result["reason"]}",
            )

        return result

    with patch(
        "homeassistant.data_entry_flow.FlowManager._async_handle_step",
        _async_handle_step,
    ):
        yield

    unused_ignore = [k for k, v in _ignore_translations.items() if v == "unused"]
    if unused_ignore:
        pytest.fail(
            f"Unused ignore translations: {', '.join(unused_ignore)}. "
            "Please remove them from the ignore_translations fixture."
        )
