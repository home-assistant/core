"""Explicit domain selection and isolation from local integration setup."""

import asyncio
from collections.abc import Generator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    MockModule,
    mock_config_flow,
    mock_integration,
    mock_platform,
)

from homeassistant import bootstrap
from homeassistant.components.sandbox._proto import sandbox_pb2 as pb
from homeassistant.components.sandbox.const import DATA_SANDBOX
from homeassistant.components.sandbox.manager import SandboxManager
from homeassistant.components.sandbox.proxy_flow import SandboxFlowProxy
from homeassistant.config_entries import (
    SOURCE_USER,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowContext,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.translation import DATA_SANDBOX_TRANSLATION_PROVIDERS
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component


@pytest.fixture
def sandbox_manager() -> Generator[MagicMock]:
    """Use a worker channel without importing or executing the integration locally."""
    manager = MagicMock(spec=SandboxManager)
    manager.shutdown_grace = 5.0
    manager.get.return_value = None
    channel = AsyncMock()
    channel.call.return_value = pb.EntrySetupResult(ok=True)
    manager.ensure_started.return_value = SimpleNamespace(channel=channel)
    with patch("homeassistant.components.sandbox.SandboxManager", return_value=manager):
        yield manager


@pytest.mark.parametrize(
    "config", [{}, {"sandbox": {}}, {"sandbox": {"integrations": []}}]
)
async def test_empty_selection_is_inactive(
    hass: HomeAssistant, sandbox_manager: MagicMock, config: ConfigType
) -> None:
    """Loading sandbox without selected domains leaves routing and providers inactive."""
    with patch("homeassistant.bootstrap.DEFAULT_INTEGRATIONS", set()):
        await bootstrap._async_set_up_integrations(hass, config)
    assert hass.config_entries.router is None
    assert DATA_SANDBOX not in hass.data
    assert DATA_SANDBOX_TRANSLATION_PROVIDERS not in hass.data
    sandbox_manager.ensure_started.assert_not_called()


@pytest.mark.parametrize("yaml", [{}, {"selected": {"yaml_only": {}}}])
@pytest.mark.parametrize("setup_name", ["async_setup", "setup"])
async def test_selected_domain_never_sets_up_locally(
    hass: HomeAssistant,
    sandbox_manager: MagicMock,
    yaml: ConfigType,
    setup_name: str,
) -> None:
    """Both setup paths are blocked, including YAML, while config entries run remotely."""
    local_setup = Mock(return_value=True)
    local_entry_setup = AsyncMock(return_value=True)
    mock_integration(
        hass,
        MockModule(
            "selected", **{setup_name: local_setup}, async_setup_entry=local_entry_setup
        ),
    )
    entry = MockConfigEntry(domain="selected")
    entry.add_to_hass(hass)
    config = {"sandbox": {"integrations": ["selected"]}, **yaml}
    assert await async_setup_component(hass, "sandbox", config)
    assert await async_setup_component(hass, "selected", config)
    assert entry.state is ConfigEntryState.LOADED
    sandbox_manager.ensure_started.assert_awaited_once_with("built-in")
    local_setup.assert_not_called()
    local_entry_setup.assert_not_called()


async def test_selected_yaml_without_entries_does_not_start_worker(
    hass: HomeAssistant, sandbox_manager: MagicMock
) -> None:
    """YAML alone cannot start a selected integration anywhere."""
    local_setup = AsyncMock(return_value=True)
    mock_integration(hass, MockModule("selected", async_setup=local_setup))
    config = {"sandbox": {"integrations": ["selected"]}, "selected": {"yaml_only": {}}}
    assert await async_setup_component(hass, "sandbox", config)
    assert await async_setup_component(hass, "selected", config)
    local_setup.assert_not_called()
    sandbox_manager.ensure_started.assert_not_called()


async def test_unselected_domain_runs_locally(
    hass: HomeAssistant, sandbox_manager: MagicMock
) -> None:
    """Enabling sandbox does not intercept another domain's YAML or config entries."""
    local_setup = AsyncMock(return_value=True)
    local_entry_setup = AsyncMock(return_value=True)
    mock_integration(
        hass,
        MockModule(
            "unselected",
            async_setup=local_setup,
            async_setup_entry=local_entry_setup,
            async_unload_entry=AsyncMock(return_value=True),
        ),
    )
    entry = MockConfigEntry(domain="unselected")
    entry.add_to_hass(hass)
    config = {"sandbox": {"integrations": ["selected"]}, "unselected": {}}
    assert await async_setup_component(hass, "sandbox", config)
    mock_platform(hass, "unselected.config_flow", None)
    with mock_config_flow("unselected", ConfigFlow):
        assert await async_setup_component(hass, "unselected", config)
    local_setup.assert_awaited_once()
    local_entry_setup.assert_awaited_once_with(hass, entry)
    sandbox_manager.ensure_started.assert_not_called()


@pytest.mark.parametrize(
    "domain",
    [
        "input_boolean",
        "input_number",
        "input_select",
        "automation",
        "camera",
        "unknown_custom",
    ],
)
async def test_explicit_selection_is_not_filtered_by_classifier(
    hass: HomeAssistant, sandbox_manager: MagicMock, domain: str
) -> None:
    """Selection accepts helper, previously excluded and custom domains alike."""
    mock_integration(hass, MockModule(domain), built_in=False)
    config = {"sandbox": {"integrations": [domain]}}
    assert await async_setup_component(hass, "sandbox", config)
    router = hass.config_entries.router
    assert router is not None
    flow = await router.async_create_flow(
        domain, context=ConfigFlowContext(source=SOURCE_USER), data=None
    )
    assert isinstance(flow, SandboxFlowProxy)
    assert (
        await router.async_create_flow(
            "unselected", context=ConfigFlowContext(source=SOURCE_USER), data=None
        )
        is None
    )
    sandbox_manager.ensure_started.assert_not_called()


@pytest.mark.parametrize(
    ("start_error", "setup_result"),
    [
        pytest.param(
            RuntimeError("Worker failed"), pb.EntrySetupResult(ok=True), id="start"
        ),
        pytest.param(
            None, pb.EntrySetupResult(ok=False, reason="Setup failed"), id="setup"
        ),
    ],
)
async def test_remote_failure_does_not_fall_back_to_local(
    hass: HomeAssistant,
    sandbox_manager: MagicMock,
    start_error: Exception | None,
    setup_result: pb.EntrySetupResult,
) -> None:
    """A selected entry stays in error when its worker cannot set it up."""
    local_setup = AsyncMock(return_value=True)
    local_entry_setup = AsyncMock(return_value=True)
    mock_integration(
        hass,
        MockModule(
            "selected", async_setup=local_setup, async_setup_entry=local_entry_setup
        ),
    )
    entry = MockConfigEntry(domain="selected")
    entry.add_to_hass(hass)
    config = {"sandbox": {"integrations": ["selected"]}, "selected": {}}
    assert await async_setup_component(hass, "sandbox", config)
    sandbox_manager.ensure_started.side_effect = start_error
    sandbox_manager.ensure_started.return_value.channel.call.return_value = setup_result
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    local_setup.assert_not_called()
    local_entry_setup.assert_not_called()


async def test_bootstrap_installs_routing_before_selected_domain(
    hass: HomeAssistant, sandbox_manager: MagicMock
) -> None:
    """Normal startup blocks local setup even before any entry has a placement tag."""
    local_setup = AsyncMock(return_value=True)
    local_entry_setup = AsyncMock(return_value=True)
    mock_integration(
        hass,
        MockModule(
            "selected", async_setup=local_setup, async_setup_entry=local_entry_setup
        ),
    )
    entry = MockConfigEntry(domain="selected")
    entry.add_to_hass(hass)
    with patch("homeassistant.bootstrap.DEFAULT_INTEGRATIONS", set()):
        await bootstrap._async_set_up_integrations(
            hass, {"sandbox": {"integrations": ["selected"]}, "selected": {}}
        )
    assert entry.state is ConfigEntryState.LOADED
    local_setup.assert_not_called()
    local_entry_setup.assert_not_called()
    sandbox_manager.ensure_started.assert_awaited_once_with("built-in")


async def test_new_selected_entry_can_register_own_domain_proxy(
    hass: HomeAssistant, sandbox_manager: MagicMock
) -> None:
    """A proxy can request its domain during entry setup without recursively setting it up."""
    local_setup = AsyncMock(return_value=True)
    mock_integration(hass, MockModule("selected", async_setup=local_setup))
    entry = MockConfigEntry(domain="selected", sandbox="built-in")
    entry.add_to_hass(hass)
    config = {"sandbox": {"integrations": ["selected"]}}
    assert await async_setup_component(hass, "sandbox", config)

    async def setup_with_proxy_registration(
        message: str, payload: pb.EntrySetup
    ) -> pb.EntrySetupResult:
        assert await async_setup_component(hass, "selected", {})
        return pb.EntrySetupResult(ok=True)

    sandbox_manager.ensure_started.return_value.channel.call.side_effect = (
        setup_with_proxy_registration
    )
    assert await asyncio.wait_for(hass.config_entries.async_setup(entry.entry_id), 1)
    assert entry.state is ConfigEntryState.LOADED
    local_setup.assert_not_called()


@pytest.mark.parametrize("load_registries", [False])
async def test_opt_in_precedes_early_bootstrap_integrations(
    hass: HomeAssistant, sandbox_manager: MagicMock
) -> None:
    """Even an integration scheduled in the earliest bootstrap phase stays remote."""
    local_setup = AsyncMock(return_value=True)
    mock_integration(hass, MockModule("selected", async_setup=local_setup))
    with (
        patch("homeassistant.bootstrap.DEFAULT_INTEGRATIONS", set()),
        patch(
            "homeassistant.bootstrap.CORE_INTEGRATIONS",
            {"homeassistant", "persistent_notification", "selected"},
        ),
    ):
        assert (
            await bootstrap.async_from_config_dict(
                {"sandbox": {"integrations": ["selected"]}, "selected": {}}, hass
            )
            is hass
        )
    local_setup.assert_not_called()
    sandbox_manager.ensure_started.assert_not_called()
