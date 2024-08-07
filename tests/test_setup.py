"""Test component/platform setup."""

import asyncio
import threading
from unittest.mock import ANY, AsyncMock, Mock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
import voluptuous as vol

from homeassistant import config_entries, loader, setup
from homeassistant.const import EVENT_COMPONENT_LOADED, EVENT_HOMEASSISTANT_START
from homeassistant.core import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    CoreState,
    HomeAssistant,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, discovery, translation
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.issue_registry import IssueRegistry

from .common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    assert_setup_component,
    mock_integration,
    mock_platform,
)


@pytest.fixture
def mock_handlers():
    """Mock config flows."""

    class MockFlowHandler(config_entries.ConfigFlow):
        """Define a mock flow handler."""

        VERSION = 1

    with patch.dict(config_entries.HANDLERS, {"comp": MockFlowHandler}):
        yield


async def test_validate_component_config(hass: HomeAssistant) -> None:
    """Test validating component configuration."""
    config_schema = vol.Schema({"comp_conf": {"hello": str}}, required=True)
    mock_integration(hass, MockModule("comp_conf", config_schema=config_schema))

    with assert_setup_component(0):
        assert not await setup.async_setup_component(hass, "comp_conf", {})

    hass.data.pop(setup.DATA_SETUP)

    with assert_setup_component(0):
        assert not await setup.async_setup_component(
            hass, "comp_conf", {"comp_conf": None}
        )

    hass.data.pop(setup.DATA_SETUP)

    with assert_setup_component(0):
        assert not await setup.async_setup_component(
            hass, "comp_conf", {"comp_conf": {}}
        )

    hass.data.pop(setup.DATA_SETUP)

    with assert_setup_component(0):
        assert not await setup.async_setup_component(
            hass,
            "comp_conf",
            {"comp_conf": {"hello": "world", "invalid": "extra"}},
        )

    hass.data.pop(setup.DATA_SETUP)

    with assert_setup_component(1):
        assert await setup.async_setup_component(
            hass, "comp_conf", {"comp_conf": {"hello": "world"}}
        )


async def test_validate_platform_config(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test validating platform configuration."""
    platform_schema = cv.PLATFORM_SCHEMA.extend({"hello": str})
    platform_schema_base = cv.PLATFORM_SCHEMA_BASE.extend({})
    mock_integration(
        hass,
        MockModule("platform_conf", platform_schema_base=platform_schema_base),
    )
    mock_platform(
        hass,
        "whatever.platform_conf",
        MockPlatform(platform_schema=platform_schema),
    )

    with assert_setup_component(0):
        assert await setup.async_setup_component(
            hass,
            "platform_conf",
            {"platform_conf": {"platform": "not_existing", "hello": "world"}},
        )

    hass.data.pop(setup.DATA_SETUP)
    hass.config.components.remove("platform_conf")

    with assert_setup_component(1):
        assert await setup.async_setup_component(
            hass,
            "platform_conf",
            {"platform_conf": {"platform": "whatever", "hello": "world"}},
        )

    hass.data.pop(setup.DATA_SETUP)
    hass.config.components.remove("platform_conf")

    with assert_setup_component(1):
        assert await setup.async_setup_component(
            hass,
            "platform_conf",
            {"platform_conf": [{"platform": "whatever", "hello": "world"}]},
        )

    hass.data.pop(setup.DATA_SETUP)
    hass.config.components.remove("platform_conf")

    # Any falsey platform config will be ignored (None, {}, etc)
    with assert_setup_component(0) as config:
        assert await setup.async_setup_component(
            hass, "platform_conf", {"platform_conf": None}
        )
        assert "platform_conf" in hass.config.components
        assert not config["platform_conf"]  # empty

        assert await setup.async_setup_component(
            hass, "platform_conf", {"platform_conf": {}}
        )
        assert "platform_conf" in hass.config.components
        assert not config["platform_conf"]  # empty


async def test_validate_platform_config_2(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test component PLATFORM_SCHEMA_BASE prio over PLATFORM_SCHEMA."""
    platform_schema = cv.PLATFORM_SCHEMA.extend({"hello": str})
    platform_schema_base = cv.PLATFORM_SCHEMA_BASE.extend({"hello": "world"})
    mock_integration(
        hass,
        MockModule(
            "platform_conf",
            platform_schema=platform_schema,
            platform_schema_base=platform_schema_base,
        ),
    )

    mock_platform(
        hass,
        "whatever.platform_conf",
        MockPlatform(platform_schema=platform_schema),
    )

    with assert_setup_component(1):
        assert await setup.async_setup_component(
            hass,
            "platform_conf",
            {
                # pass
                "platform_conf": {"platform": "whatever", "hello": "world"},
                # fail: key hello violates component platform_schema_base
                "platform_conf 2": {"platform": "whatever", "hello": "there"},
            },
        )


async def test_validate_platform_config_3(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test fallback to component PLATFORM_SCHEMA."""
    component_schema = cv.PLATFORM_SCHEMA_BASE.extend({"hello": str})
    platform_schema = cv.PLATFORM_SCHEMA.extend({"cheers": str, "hello": "world"})
    mock_integration(
        hass, MockModule("platform_conf", platform_schema=component_schema)
    )

    mock_platform(
        hass,
        "whatever.platform_conf",
        MockPlatform(platform_schema=platform_schema),
    )

    with assert_setup_component(1):
        assert await setup.async_setup_component(
            hass,
            "platform_conf",
            {
                # pass
                "platform_conf": {"platform": "whatever", "hello": "world"},
                # fail: key hello violates component platform_schema
                "platform_conf 2": {"platform": "whatever", "hello": "there"},
            },
        )


async def test_validate_platform_config_4(hass: HomeAssistant) -> None:
    """Test entity_namespace in PLATFORM_SCHEMA."""
    component_schema = cv.PLATFORM_SCHEMA_BASE
    platform_schema = cv.PLATFORM_SCHEMA
    mock_integration(
        hass,
        MockModule("platform_conf", platform_schema_base=component_schema),
    )

    mock_platform(
        hass,
        "whatever.platform_conf",
        MockPlatform(platform_schema=platform_schema),
    )

    with assert_setup_component(1):
        assert await setup.async_setup_component(
            hass,
            "platform_conf",
            {
                "platform_conf": {
                    # pass: entity_namespace accepted by PLATFORM_SCHEMA
                    "platform": "whatever",
                    "entity_namespace": "yummy",
                }
            },
        )

    hass.data.pop(setup.DATA_SETUP)
    hass.config.components.remove("platform_conf")


async def test_component_not_found(
    hass: HomeAssistant, issue_registry: IssueRegistry
) -> None:
    """setup_component should raise a repair issue if component doesn't exist."""
    assert await setup.async_setup_component(hass, "non_existing", {}) is False
    assert len(issue_registry.issues) == 1
    issue = issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN, "integration_not_found.non_existing"
    )
    assert issue
    assert issue.translation_key == "integration_not_found"


async def test_component_missing_not_raising_in_safe_mode(
    hass: HomeAssistant, issue_registry: IssueRegistry
) -> None:
    """setup_component should not raise an issue if component doesn't exist in safe."""
    hass.config.safe_mode = True
    assert await setup.async_setup_component(hass, "non_existing", {}) is False
    assert len(issue_registry.issues) == 0


async def test_component_not_double_initialized(hass: HomeAssistant) -> None:
    """Test we do not set up a component twice."""
    mock_setup = Mock(return_value=True)

    mock_integration(hass, MockModule("comp", setup=mock_setup))

    assert await setup.async_setup_component(hass, "comp", {})
    assert mock_setup.called

    mock_setup.reset_mock()

    assert await setup.async_setup_component(hass, "comp", {})
    assert not mock_setup.called


async def test_component_not_installed_if_requirement_fails(
    hass: HomeAssistant,
) -> None:
    """Component setup should fail if requirement can't install."""
    hass.config.skip_pip = False
    mock_integration(hass, MockModule("comp", requirements=["package==0.0.1"]))

    with patch("homeassistant.util.package.install_package", return_value=False):
        assert not await setup.async_setup_component(hass, "comp", {})

    assert "comp" not in hass.config.components


async def test_component_not_setup_twice_if_loaded_during_other_setup(
    hass: HomeAssistant,
) -> None:
    """Test component setup while waiting for lock is not set up twice."""
    result = []

    async def async_setup(hass, config):
        """Tracking Setup."""
        result.append(1)

    mock_integration(hass, MockModule("comp", async_setup=async_setup))

    def setup_component():
        """Set up the component."""
        setup.setup_component(hass, "comp", {})

    thread = threading.Thread(target=setup_component)
    thread.start()
    await setup.async_setup_component(hass, "comp", {})

    await hass.async_add_executor_job(thread.join)

    assert len(result) == 1


async def test_component_not_setup_missing_dependencies(hass: HomeAssistant) -> None:
    """Test we do not set up a component if not all dependencies loaded."""
    deps = ["maybe_existing"]
    mock_integration(hass, MockModule("comp", dependencies=deps))

    assert not await setup.async_setup_component(hass, "comp", {})
    assert "comp" not in hass.config.components

    hass.data.pop(setup.DATA_SETUP)

    mock_integration(hass, MockModule("comp2", dependencies=deps))
    mock_integration(hass, MockModule("maybe_existing"))

    assert await setup.async_setup_component(hass, "comp2", {})


async def test_component_failing_setup(hass: HomeAssistant) -> None:
    """Test component that fails setup."""
    mock_integration(hass, MockModule("comp", setup=lambda hass, config: False))

    assert not await setup.async_setup_component(hass, "comp", {})
    assert "comp" not in hass.config.components


async def test_component_exception_setup(hass: HomeAssistant) -> None:
    """Test component that raises exception during setup."""
    setup.async_set_domains_to_be_loaded(hass, {"comp"})

    def exception_setup(hass, config):
        """Raise exception."""
        raise Exception("fail!")  # pylint: disable=broad-exception-raised

    mock_integration(hass, MockModule("comp", setup=exception_setup))

    assert not await setup.async_setup_component(hass, "comp", {})
    assert "comp" not in hass.config.components


async def test_component_base_exception_setup(hass: HomeAssistant) -> None:
    """Test component that raises exception during setup."""
    setup.async_set_domains_to_be_loaded(hass, {"comp"})

    def exception_setup(hass, config):
        """Raise exception."""
        raise BaseException("fail!")  # pylint: disable=broad-exception-raised

    mock_integration(hass, MockModule("comp", setup=exception_setup))

    with pytest.raises(BaseException) as exc_info:
        await setup.async_setup_component(hass, "comp", {})
    assert str(exc_info.value) == "fail!"

    assert "comp" not in hass.config.components


async def test_component_setup_with_validation_and_dependency(
    hass: HomeAssistant,
) -> None:
    """Test all config is passed to dependencies."""

    def config_check_setup(hass, config):
        """Test that config is passed in."""
        if config.get("comp_a", {}).get("valid", False):
            return True
        # pylint: disable-next=broad-exception-raised
        raise Exception(f"Config not passed in: {config}")

    platform = MockPlatform()

    mock_integration(hass, MockModule("comp_a", setup=config_check_setup))
    mock_integration(
        hass,
        MockModule("platform_a", setup=config_check_setup, dependencies=["comp_a"]),
    )

    mock_platform(hass, "platform_a.switch", platform)

    await setup.async_setup_component(
        hass,
        "switch",
        {"comp_a": {"valid": True}, "switch": {"platform": "platform_a"}},
    )
    await hass.async_block_till_done()
    assert "comp_a" in hass.config.components


async def test_platform_specific_config_validation(hass: HomeAssistant) -> None:
    """Test platform that specifies config."""
    platform_schema = cv.PLATFORM_SCHEMA.extend(
        {"valid": True}, extra=vol.PREVENT_EXTRA
    )

    mock_setup = Mock(spec_set=True)

    mock_platform(
        hass,
        "platform_a.switch",
        MockPlatform(platform_schema=platform_schema, setup_platform=mock_setup),
    )

    with (
        assert_setup_component(0, "switch"),
        patch("homeassistant.setup.async_notify_setup_error") as mock_notify,
    ):
        assert await setup.async_setup_component(
            hass,
            "switch",
            {"switch": {"platform": "platform_a", "invalid": True}},
        )
        await hass.async_block_till_done()
        assert mock_setup.call_count == 0
        assert len(mock_notify.mock_calls) == 1

    hass.data.pop(setup.DATA_SETUP)
    hass.config.components.remove("switch")

    with (
        assert_setup_component(0),
        patch("homeassistant.setup.async_notify_setup_error") as mock_notify,
    ):
        assert await setup.async_setup_component(
            hass,
            "switch",
            {
                "switch": {
                    "platform": "platform_a",
                    "valid": True,
                    "invalid_extra": True,
                }
            },
        )
        await hass.async_block_till_done()
        assert mock_setup.call_count == 0
        assert len(mock_notify.mock_calls) == 1

    hass.data.pop(setup.DATA_SETUP)
    hass.config.components.remove("switch")

    with (
        assert_setup_component(1, "switch"),
        patch("homeassistant.setup.async_notify_setup_error") as mock_notify,
    ):
        assert await setup.async_setup_component(
            hass,
            "switch",
            {"switch": {"platform": "platform_a", "valid": True}},
        )
        await hass.async_block_till_done()
        assert mock_setup.call_count == 1
        assert len(mock_notify.mock_calls) == 0


async def test_disable_component_if_invalid_return(hass: HomeAssistant) -> None:
    """Test disabling component if invalid return."""
    mock_integration(
        hass, MockModule("disabled_component", setup=lambda hass, config: None)
    )

    assert not await setup.async_setup_component(hass, "disabled_component", {})
    assert "disabled_component" not in hass.config.components

    hass.data.pop(setup.DATA_SETUP)
    mock_integration(
        hass,
        MockModule("disabled_component", setup=lambda hass, config: False),
    )

    assert not await setup.async_setup_component(hass, "disabled_component", {})
    assert "disabled_component" not in hass.config.components

    hass.data.pop(setup.DATA_SETUP)
    mock_integration(
        hass, MockModule("disabled_component", setup=lambda hass, config: True)
    )

    assert await setup.async_setup_component(hass, "disabled_component", {})
    assert "disabled_component" in hass.config.components


async def test_all_work_done_before_start(hass: HomeAssistant) -> None:
    """Test all init work done till start."""
    call_order = []

    async def component1_setup(hass, config):
        """Set up mock component."""
        await discovery.async_discover(
            hass, "test_component2", {}, "test_component2", {}
        )
        await discovery.async_discover(
            hass, "test_component3", {}, "test_component3", {}
        )
        return True

    def component_track_setup(hass, config):
        """Set up mock component."""
        call_order.append(1)
        return True

    mock_integration(hass, MockModule("test_component1", async_setup=component1_setup))

    mock_integration(hass, MockModule("test_component2", setup=component_track_setup))

    mock_integration(hass, MockModule("test_component3", setup=component_track_setup))

    @callback
    def track_start(event):
        """Track start event."""
        call_order.append(2)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, track_start)

    hass.add_job(setup.async_setup_component(hass, "test_component1", {}))
    await hass.async_block_till_done()
    await hass.async_start()
    assert call_order == [1, 1, 2]


async def test_component_warn_slow_setup(hass: HomeAssistant) -> None:
    """Warn we log when a component setup takes a long time."""
    mock_integration(hass, MockModule("test_component1"))
    with patch.object(hass.loop, "call_later") as mock_call:
        result = await setup.async_setup_component(hass, "test_component1", {})
        assert result
        assert mock_call.called

        assert len(mock_call.mock_calls) == 3
        timeout, logger_method = mock_call.mock_calls[0][1][:2]

        assert timeout == setup.SLOW_SETUP_WARNING
        assert logger_method == setup._LOGGER.warning

        assert mock_call().cancel.called


async def test_platform_no_warn_slow(hass: HomeAssistant) -> None:
    """Do not warn for long entity setup time."""
    mock_integration(
        hass, MockModule("test_component1", platform_schema=cv.PLATFORM_SCHEMA)
    )
    with patch.object(hass.loop, "call_later") as mock_call:
        result = await setup.async_setup_component(hass, "test_component1", {})
        assert result
        assert len(mock_call.mock_calls) == 0


async def test_platform_error_slow_setup(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Don't block startup more than SLOW_SETUP_MAX_WAIT."""

    with patch.object(setup, "SLOW_SETUP_MAX_WAIT", 0.1):
        called = []

        async def async_setup(*args):
            """Tracking Setup."""
            called.append(1)
            await asyncio.sleep(2)

        mock_integration(hass, MockModule("test_component1", async_setup=async_setup))
        result = await setup.async_setup_component(hass, "test_component1", {})
        assert len(called) == 1
        assert not result
        assert "'test_component1' is taking longer than 0.1 seconds" in caplog.text


async def test_when_setup_already_loaded(hass: HomeAssistant) -> None:
    """Test when setup."""
    calls = []

    async def mock_callback(hass, component):
        """Mock callback."""
        calls.append(component)

    setup.async_when_setup(hass, "test", mock_callback)
    await hass.async_block_till_done()
    assert calls == []

    hass.config.components.add("test")
    hass.bus.async_fire(EVENT_COMPONENT_LOADED, {"component": "test"})
    await hass.async_block_till_done()
    assert calls == ["test"]

    # Event listener should be gone
    hass.bus.async_fire(EVENT_COMPONENT_LOADED, {"component": "test"})
    await hass.async_block_till_done()
    assert calls == ["test"]

    # Should be called right away
    setup.async_when_setup(hass, "test", mock_callback)
    await hass.async_block_till_done()
    assert calls == ["test", "test"]


async def test_async_when_setup_or_start_already_loaded(hass: HomeAssistant) -> None:
    """Test when setup or start."""
    calls = []

    async def mock_callback(hass, component):
        """Mock callback."""
        calls.append(component)

    setup.async_when_setup_or_start(hass, "test", mock_callback)
    await hass.async_block_till_done()
    assert calls == []

    hass.config.components.add("test")
    hass.bus.async_fire(EVENT_COMPONENT_LOADED, {"component": "test"})
    await hass.async_block_till_done()
    assert calls == ["test"]

    # Event listener should be gone
    hass.bus.async_fire(EVENT_COMPONENT_LOADED, {"component": "test"})
    await hass.async_block_till_done()
    assert calls == ["test"]

    # Should be called right away
    setup.async_when_setup_or_start(hass, "test", mock_callback)
    await hass.async_block_till_done()
    assert calls == ["test", "test"]

    setup.async_when_setup_or_start(hass, "not_loaded", mock_callback)
    await hass.async_block_till_done()
    assert calls == ["test", "test"]
    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    assert calls == ["test", "test", "not_loaded"]


async def test_setup_import_blows_up(hass: HomeAssistant) -> None:
    """Test that we handle it correctly when importing integration blows up."""
    with patch(
        "homeassistant.loader.Integration.async_get_component", side_effect=ImportError
    ):
        assert not await setup.async_setup_component(hass, "sun", {})


async def test_parallel_entry_setup(hass: HomeAssistant, mock_handlers) -> None:
    """Test config entries are set up in parallel."""
    MockConfigEntry(domain="comp", data={"value": 1}).add_to_hass(hass)
    MockConfigEntry(domain="comp", data={"value": 2}).add_to_hass(hass)

    calls = []

    async def mock_async_setup_entry(hass, entry):
        """Mock setting up an entry."""
        calls.append(entry.data["value"])
        await asyncio.sleep(0)
        calls.append(entry.data["value"])
        return True

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup_entry=mock_async_setup_entry,
        ),
    )
    mock_platform(hass, "comp.config_flow", None)
    await setup.async_setup_component(hass, "comp", {})

    assert calls == [1, 2, 1, 2]


async def test_integration_disabled(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we can disable an integration."""
    disabled_reason = "Dependency contains code that breaks Home Assistant"
    mock_integration(
        hass,
        MockModule("test_component1", partial_manifest={"disabled": disabled_reason}),
    )
    result = await setup.async_setup_component(hass, "test_component1", {})
    assert not result
    assert disabled_reason in caplog.text


async def test_integration_logs_is_custom(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we highlight it's a custom component when errors happen."""
    mock_integration(
        hass,
        MockModule("test_component1"),
        built_in=False,
    )
    with patch(
        "homeassistant.setup.async_process_deps_reqs",
        side_effect=HomeAssistantError("Boom"),
    ):
        result = await setup.async_setup_component(hass, "test_component1", {})
    assert not result
    assert "Setup failed for custom integration 'test_component1': Boom" in caplog.text


async def test_async_get_loaded_integrations(hass: HomeAssistant) -> None:
    """Test we can enumerate loaded integrations."""
    hass.config.components.add("notbase")
    hass.config.components.add("switch")
    hass.config.components.add("notbase.switch")
    hass.config.components.add("myintegration")
    hass.config.components.add("device_tracker")
    hass.config.components.add("other.device_tracker")
    hass.config.components.add("myintegration.light")
    assert setup.async_get_loaded_integrations(hass) == {
        "other",
        "switch",
        "notbase",
        "myintegration",
        "device_tracker",
    }


async def test_integration_no_setup(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we fail integration setup without setup functions."""
    mock_integration(
        hass,
        MockModule("test_integration_without_setup", setup=False),
    )
    result = await setup.async_setup_component(
        hass, "test_integration_without_setup", {}
    )
    assert not result
    assert "No setup or config entry setup function defined" in caplog.text


async def test_integration_only_setup_entry(hass: HomeAssistant) -> None:
    """Test we have an integration with only a setup entry method."""
    mock_integration(
        hass,
        MockModule(
            "test_integration_only_entry",
            setup=False,
            async_setup_entry=AsyncMock(return_value=True),
        ),
    )
    assert await setup.async_setup_component(hass, "test_integration_only_entry", {})


async def test_async_start_setup_running(hass: HomeAssistant) -> None:
    """Test setup started context manager does nothing when running."""
    assert hass.state is CoreState.running
    setup_started = hass.data.setdefault(setup.DATA_SETUP_STARTED, {})

    with setup.async_start_setup(
        hass, integration="august", phase=setup.SetupPhases.SETUP
    ):
        assert not setup_started


async def test_async_start_setup_config_entry(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test setup started keeps track of setup times with a config entry."""
    hass.set_state(CoreState.not_running)
    setup_started = hass.data.setdefault(setup.DATA_SETUP_STARTED, {})
    setup_time = setup._setup_times(hass)

    with setup.async_start_setup(
        hass, integration="august", phase=setup.SetupPhases.SETUP
    ):
        assert isinstance(setup_started[("august", None)], float)

    with setup.async_start_setup(
        hass,
        integration="august",
        group="entry_id",
        phase=setup.SetupPhases.CONFIG_ENTRY_SETUP,
    ):
        assert isinstance(setup_started[("august", "entry_id")], float)
        with setup.async_start_setup(
            hass,
            integration="august",
            group="entry_id",
            phase=setup.SetupPhases.CONFIG_ENTRY_PLATFORM_SETUP,
        ):
            assert isinstance(setup_started[("august", "entry_id")], float)

    # CONFIG_ENTRY_PLATFORM_SETUP inside of CONFIG_ENTRY_SETUP should not be tracked
    assert setup_time["august"] == {
        None: {setup.SetupPhases.SETUP: ANY},
        "entry_id": {setup.SetupPhases.CONFIG_ENTRY_SETUP: ANY},
    }
    with setup.async_start_setup(
        hass,
        integration="august",
        group="entry_id",
        phase=setup.SetupPhases.CONFIG_ENTRY_PLATFORM_SETUP,
    ):
        assert isinstance(setup_started[("august", "entry_id")], float)

    # Platforms outside of CONFIG_ENTRY_SETUP should be tracked
    # This simulates a late platform forward
    assert setup_time["august"] == {
        None: {setup.SetupPhases.SETUP: ANY},
        "entry_id": {
            setup.SetupPhases.CONFIG_ENTRY_SETUP: ANY,
            setup.SetupPhases.CONFIG_ENTRY_PLATFORM_SETUP: ANY,
        },
    }

    shorter_time = setup_time["august"]["entry_id"][
        setup.SetupPhases.CONFIG_ENTRY_PLATFORM_SETUP
    ]
    # Setup another platform, but make it take longer
    with setup.async_start_setup(
        hass,
        integration="august",
        group="entry_id",
        phase=setup.SetupPhases.CONFIG_ENTRY_PLATFORM_SETUP,
    ):
        freezer.tick(10)
        assert isinstance(setup_started[("august", "entry_id")], float)

    longer_time = setup_time["august"]["entry_id"][
        setup.SetupPhases.CONFIG_ENTRY_PLATFORM_SETUP
    ]
    assert longer_time > shorter_time
    # Setup another platform, but make it take shorter
    with setup.async_start_setup(
        hass,
        integration="august",
        group="entry_id",
        phase=setup.SetupPhases.CONFIG_ENTRY_PLATFORM_SETUP,
    ):
        assert isinstance(setup_started[("august", "entry_id")], float)

    # Ensure we keep the longest time
    assert (
        setup_time["august"]["entry_id"][setup.SetupPhases.CONFIG_ENTRY_PLATFORM_SETUP]
        == longer_time
    )

    with setup.async_start_setup(
        hass,
        integration="august",
        group="entry_id2",
        phase=setup.SetupPhases.CONFIG_ENTRY_SETUP,
    ):
        assert isinstance(setup_started[("august", "entry_id2")], float)
        # We wrap places where we wait for other components
        # or the import of a module with async_freeze_setup
        # so we can subtract the time waited from the total setup time
        with setup.async_pause_setup(hass, setup.SetupPhases.WAIT_BASE_PLATFORM_SETUP):
            await asyncio.sleep(0)

    # Wait time should be added if freeze_setup is used
    assert setup_time["august"] == {
        None: {setup.SetupPhases.SETUP: ANY},
        "entry_id": {
            setup.SetupPhases.CONFIG_ENTRY_SETUP: ANY,
            setup.SetupPhases.CONFIG_ENTRY_PLATFORM_SETUP: ANY,
        },
        "entry_id2": {
            setup.SetupPhases.CONFIG_ENTRY_SETUP: ANY,
            setup.SetupPhases.WAIT_BASE_PLATFORM_SETUP: ANY,
        },
    }


async def test_async_start_setup_config_entry_late_platform(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test setup started tracks config entry time with a late platform load."""
    hass.set_state(CoreState.not_running)
    setup_started = hass.data.setdefault(setup.DATA_SETUP_STARTED, {})
    setup_time = setup._setup_times(hass)

    with setup.async_start_setup(
        hass, integration="august", phase=setup.SetupPhases.SETUP
    ):
        freezer.tick(10)
        assert isinstance(setup_started[("august", None)], float)

    with setup.async_start_setup(
        hass,
        integration="august",
        group="entry_id",
        phase=setup.SetupPhases.CONFIG_ENTRY_SETUP,
    ):
        assert isinstance(setup_started[("august", "entry_id")], float)

        @callback
        def async_late_platform_load():
            with setup.async_pause_setup(hass, setup.SetupPhases.WAIT_IMPORT_PLATFORMS):
                freezer.tick(100)
            with setup.async_start_setup(
                hass,
                integration="august",
                group="entry_id",
                phase=setup.SetupPhases.CONFIG_ENTRY_PLATFORM_SETUP,
            ):
                freezer.tick(20)
                assert isinstance(setup_started[("august", "entry_id")], float)

        disconnect = async_dispatcher_connect(
            hass, "late_platform_load_test", async_late_platform_load
        )

    # Dispatch a late platform load
    async_dispatcher_send(hass, "late_platform_load_test")
    disconnect()

    # CONFIG_ENTRY_PLATFORM_SETUP is late dispatched, so it should be tracked
    # but any waiting time should not be because it's blocking the setup
    assert setup_time["august"] == {
        None: {setup.SetupPhases.SETUP: 10.0},
        "entry_id": {
            setup.SetupPhases.CONFIG_ENTRY_PLATFORM_SETUP: 20.0,
            setup.SetupPhases.CONFIG_ENTRY_SETUP: 0.0,
        },
    }


async def test_async_start_setup_config_entry_platform_wait(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test setup started tracks wait time when a platform loads inside of config entry setup."""
    hass.set_state(CoreState.not_running)
    setup_started = hass.data.setdefault(setup.DATA_SETUP_STARTED, {})
    setup_time = setup._setup_times(hass)

    with setup.async_start_setup(
        hass, integration="august", phase=setup.SetupPhases.SETUP
    ):
        freezer.tick(10)
        assert isinstance(setup_started[("august", None)], float)

    with setup.async_start_setup(
        hass,
        integration="august",
        group="entry_id",
        phase=setup.SetupPhases.CONFIG_ENTRY_SETUP,
    ):
        assert isinstance(setup_started[("august", "entry_id")], float)

        with setup.async_pause_setup(hass, setup.SetupPhases.WAIT_IMPORT_PLATFORMS):
            freezer.tick(100)
        with setup.async_start_setup(
            hass,
            integration="august",
            group="entry_id",
            phase=setup.SetupPhases.CONFIG_ENTRY_PLATFORM_SETUP,
        ):
            freezer.tick(20)
            assert isinstance(setup_started[("august", "entry_id")], float)

    # CONFIG_ENTRY_PLATFORM_SETUP is run inside of CONFIG_ENTRY_SETUP, so it should not
    # be tracked, but any wait time should still be tracked because its blocking the setup
    assert setup_time["august"] == {
        None: {setup.SetupPhases.SETUP: 10.0},
        "entry_id": {
            setup.SetupPhases.WAIT_IMPORT_PLATFORMS: -100.0,
            setup.SetupPhases.CONFIG_ENTRY_SETUP: 120.0,
        },
    }


async def test_async_start_setup_top_level_yaml(hass: HomeAssistant) -> None:
    """Test setup started context manager keeps track of setup times with modern yaml."""
    hass.set_state(CoreState.not_running)
    setup_started = hass.data.setdefault(setup.DATA_SETUP_STARTED, {})
    setup_time = setup._setup_times(hass)

    with setup.async_start_setup(
        hass, integration="command_line", phase=setup.SetupPhases.SETUP
    ):
        assert isinstance(setup_started[("command_line", None)], float)

    assert setup_time["command_line"] == {
        None: {setup.SetupPhases.SETUP: ANY},
    }


async def test_async_start_setup_platform_integration(hass: HomeAssistant) -> None:
    """Test setup started keeps track of setup times a platform integration."""
    hass.set_state(CoreState.not_running)
    setup_started = hass.data.setdefault(setup.DATA_SETUP_STARTED, {})
    setup_time = setup._setup_times(hass)

    with setup.async_start_setup(
        hass, integration="sensor", phase=setup.SetupPhases.SETUP
    ):
        assert isinstance(setup_started[("sensor", None)], float)

    # Platform integration setups happen in another task
    with setup.async_start_setup(
        hass,
        integration="filter",
        group="123456",
        phase=setup.SetupPhases.PLATFORM_SETUP,
    ):
        assert isinstance(setup_started[("filter", "123456")], float)

    assert setup_time["sensor"] == {
        None: {
            setup.SetupPhases.SETUP: ANY,
        },
    }
    assert setup_time["filter"] == {
        "123456": {
            setup.SetupPhases.PLATFORM_SETUP: ANY,
        },
    }


async def test_async_start_setup_legacy_platform_integration(
    hass: HomeAssistant,
) -> None:
    """Test setup started keeps track of setup times for a legacy platform integration."""
    hass.set_state(CoreState.not_running)
    setup_started = hass.data.setdefault(setup.DATA_SETUP_STARTED, {})
    setup_time = setup._setup_times(hass)

    with setup.async_start_setup(
        hass, integration="notify", phase=setup.SetupPhases.SETUP
    ):
        assert isinstance(setup_started[("notify", None)], float)

    with setup.async_start_setup(
        hass,
        integration="legacy_notify_integration",
        group="123456",
        phase=setup.SetupPhases.PLATFORM_SETUP,
    ):
        assert isinstance(setup_started[("legacy_notify_integration", "123456")], float)

    assert setup_time["notify"] == {
        None: {
            setup.SetupPhases.SETUP: ANY,
        },
    }
    assert setup_time["legacy_notify_integration"] == {
        "123456": {
            setup.SetupPhases.PLATFORM_SETUP: ANY,
        },
    }


async def test_async_start_setup_simple_integration_end_to_end(
    hass: HomeAssistant,
) -> None:
    """Test end to end timings for a simple integration with no platforms."""
    hass.set_state(CoreState.not_running)
    mock_integration(
        hass,
        MockModule(
            "test_integration_no_platforms",
            setup=False,
            async_setup_entry=AsyncMock(return_value=True),
        ),
    )
    assert await setup.async_setup_component(hass, "test_integration_no_platforms", {})
    await hass.async_block_till_done()
    assert setup.async_get_setup_timings(hass) == {
        "test_integration_no_platforms": ANY,
    }


async def test_async_get_setup_timings(hass: HomeAssistant) -> None:
    """Test we can get the setup timings from the setup time data."""
    setup_time = setup._setup_times(hass)
    # Mock setup time data
    setup_time.update(
        {
            "august": {
                None: {setup.SetupPhases.SETUP: 1},
                "entry_id": {
                    setup.SetupPhases.CONFIG_ENTRY_SETUP: 1,
                    setup.SetupPhases.CONFIG_ENTRY_PLATFORM_SETUP: 4,
                },
                "entry_id2": {
                    setup.SetupPhases.CONFIG_ENTRY_SETUP: 7,
                    setup.SetupPhases.WAIT_BASE_PLATFORM_SETUP: -5,
                },
            },
            "notify": {
                None: {
                    setup.SetupPhases.SETUP: 2,
                },
            },
            "legacy_notify_integration": {
                "123456": {
                    setup.SetupPhases.PLATFORM_SETUP: 3,
                },
            },
            "sensor": {
                None: {
                    setup.SetupPhases.SETUP: 1,
                },
            },
            "filter": {
                "123456": {
                    setup.SetupPhases.PLATFORM_SETUP: 2,
                },
            },
        }
    )
    assert setup.async_get_setup_timings(hass) == {
        "august": 6,
        "notify": 2,
        "legacy_notify_integration": 3,
        "sensor": 1,
        "filter": 2,
    }
    assert setup.async_get_domain_setup_times(hass, "filter") == {
        "123456": {
            setup.SetupPhases.PLATFORM_SETUP: 2,
        },
    }


async def test_setup_config_entry_from_yaml(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test attempting to setup an integration which only supports config_entries."""
    expected_warning = (
        "The 'test_integration_only_entry' integration does not support YAML setup, "
        "please remove it from your configuration"
    )

    mock_integration(
        hass,
        MockModule(
            "test_integration_only_entry",
            setup=False,
            async_setup_entry=AsyncMock(return_value=True),
        ),
    )

    assert await setup.async_setup_component(hass, "test_integration_only_entry", {})
    assert expected_warning not in caplog.text
    caplog.clear()
    hass.data.pop(setup.DATA_SETUP)
    hass.config.components.remove("test_integration_only_entry")

    # There should be a warning, but setup should not fail
    assert await setup.async_setup_component(
        hass, "test_integration_only_entry", {"test_integration_only_entry": None}
    )
    assert expected_warning in caplog.text
    caplog.clear()
    hass.data.pop(setup.DATA_SETUP)
    hass.config.components.remove("test_integration_only_entry")

    # There should be a warning, but setup should not fail
    assert await setup.async_setup_component(
        hass, "test_integration_only_entry", {"test_integration_only_entry": {}}
    )
    assert expected_warning in caplog.text
    caplog.clear()
    hass.data.pop(setup.DATA_SETUP)
    hass.config.components.remove("test_integration_only_entry")

    # There should be a warning, but setup should not fail
    assert await setup.async_setup_component(
        hass,
        "test_integration_only_entry",
        {"test_integration_only_entry": {"hello": "world"}},
    )
    assert expected_warning in caplog.text
    caplog.clear()
    hass.data.pop(setup.DATA_SETUP)
    hass.config.components.remove("test_integration_only_entry")


async def test_loading_component_loads_translations(hass: HomeAssistant) -> None:
    """Test that loading a component loads translations."""
    assert translation.async_translations_loaded(hass, {"comp"}) is False
    mock_setup = Mock(return_value=True)

    mock_integration(hass, MockModule("comp", setup=mock_setup))
    integration = await loader.async_get_integration(hass, "comp")
    with patch.object(integration, "has_translations", True):
        assert await setup.async_setup_component(hass, "comp", {})
    assert mock_setup.called
    assert translation.async_translations_loaded(hass, {"comp"}) is True


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_importing_integration_in_executor(hass: HomeAssistant) -> None:
    """Test we can import an integration in an executor."""
    assert await setup.async_setup_component(hass, "test_package_loaded_executor", {})
    assert await setup.async_setup_component(hass, "test_package_loaded_executor", {})
    await hass.async_block_till_done()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_async_prepare_setup_platform(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we can prepare a platform setup."""
    integration = await loader.async_get_integration(hass, "test")
    with patch.object(
        integration, "async_get_component", side_effect=ImportError("test is broken")
    ):
        assert (
            await setup.async_prepare_setup_platform(hass, {}, "config", "test") is None
        )

    assert "test is broken" in caplog.text

    caplog.clear()
    # There is no actual config platform for this integration
    assert await setup.async_prepare_setup_platform(hass, {}, "config", "test") is None
    assert "No module named 'custom_components.test.config'" in caplog.text

    button_platform = (
        await setup.async_prepare_setup_platform(hass, {}, "button", "test") is None
    )
    assert button_platform is not None
