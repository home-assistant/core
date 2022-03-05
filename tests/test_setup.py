"""Test component/platform setup."""
# pylint: disable=protected-access
import asyncio
import datetime
import threading
from unittest.mock import AsyncMock, Mock, patch

import pytest
import voluptuous as vol

from homeassistant import config_entries, setup
from homeassistant.const import EVENT_COMPONENT_LOADED, EVENT_HOMEASSISTANT_START
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import discovery
from homeassistant.helpers.config_validation import (
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    assert_setup_component,
    mock_entity_platform,
    mock_integration,
)


@pytest.fixture
def mock_handlers():
    """Mock config flows."""

    class MockFlowHandler(config_entries.ConfigFlow):
        """Define a mock flow handler."""

        VERSION = 1

    with patch.dict(config_entries.HANDLERS, {"comp": MockFlowHandler}):
        yield


async def test_validate_component_config(hass):
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


async def test_validate_platform_config(hass, caplog):
    """Test validating platform configuration."""
    platform_schema = PLATFORM_SCHEMA.extend({"hello": str})
    platform_schema_base = PLATFORM_SCHEMA_BASE.extend({})
    mock_integration(
        hass,
        MockModule("platform_conf", platform_schema_base=platform_schema_base),
    )
    mock_entity_platform(
        hass,
        "platform_conf.whatever",
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


async def test_validate_platform_config_2(hass, caplog):
    """Test component PLATFORM_SCHEMA_BASE prio over PLATFORM_SCHEMA."""
    platform_schema = PLATFORM_SCHEMA.extend({"hello": str})
    platform_schema_base = PLATFORM_SCHEMA_BASE.extend({"hello": "world"})
    mock_integration(
        hass,
        MockModule(
            "platform_conf",
            platform_schema=platform_schema,
            platform_schema_base=platform_schema_base,
        ),
    )

    mock_entity_platform(
        hass,
        "platform_conf.whatever",
        MockPlatform("whatever", platform_schema=platform_schema),
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


async def test_validate_platform_config_3(hass, caplog):
    """Test fallback to component PLATFORM_SCHEMA."""
    component_schema = PLATFORM_SCHEMA_BASE.extend({"hello": str})
    platform_schema = PLATFORM_SCHEMA.extend({"cheers": str, "hello": "world"})
    mock_integration(
        hass, MockModule("platform_conf", platform_schema=component_schema)
    )

    mock_entity_platform(
        hass,
        "platform_conf.whatever",
        MockPlatform("whatever", platform_schema=platform_schema),
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


async def test_validate_platform_config_4(hass):
    """Test entity_namespace in PLATFORM_SCHEMA."""
    component_schema = PLATFORM_SCHEMA_BASE
    platform_schema = PLATFORM_SCHEMA
    mock_integration(
        hass,
        MockModule("platform_conf", platform_schema_base=component_schema),
    )

    mock_entity_platform(
        hass,
        "platform_conf.whatever",
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


async def test_component_not_found(hass):
    """setup_component should not crash if component doesn't exist."""
    assert await setup.async_setup_component(hass, "non_existing", {}) is False


async def test_component_not_double_initialized(hass):
    """Test we do not set up a component twice."""
    mock_setup = Mock(return_value=True)

    mock_integration(hass, MockModule("comp", setup=mock_setup))

    assert await setup.async_setup_component(hass, "comp", {})
    assert mock_setup.called

    mock_setup.reset_mock()

    assert await setup.async_setup_component(hass, "comp", {})
    assert not mock_setup.called


async def test_component_not_installed_if_requirement_fails(hass):
    """Component setup should fail if requirement can't install."""
    hass.config.skip_pip = False
    mock_integration(hass, MockModule("comp", requirements=["package==0.0.1"]))

    with patch("homeassistant.util.package.install_package", return_value=False):
        assert not await setup.async_setup_component(hass, "comp", {})

    assert "comp" not in hass.config.components


async def test_component_not_setup_twice_if_loaded_during_other_setup(hass):
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


async def test_component_not_setup_missing_dependencies(hass):
    """Test we do not set up a component if not all dependencies loaded."""
    deps = ["maybe_existing"]
    mock_integration(hass, MockModule("comp", dependencies=deps))

    assert not await setup.async_setup_component(hass, "comp", {})
    assert "comp" not in hass.config.components

    hass.data.pop(setup.DATA_SETUP)

    mock_integration(hass, MockModule("comp2", dependencies=deps))
    mock_integration(hass, MockModule("maybe_existing"))

    assert await setup.async_setup_component(hass, "comp2", {})


async def test_component_failing_setup(hass):
    """Test component that fails setup."""
    mock_integration(hass, MockModule("comp", setup=lambda hass, config: False))

    assert not await setup.async_setup_component(hass, "comp", {})
    assert "comp" not in hass.config.components


async def test_component_exception_setup(hass):
    """Test component that raises exception during setup."""

    def exception_setup(hass, config):
        """Raise exception."""
        raise Exception("fail!")

    mock_integration(hass, MockModule("comp", setup=exception_setup))

    assert not await setup.async_setup_component(hass, "comp", {})
    assert "comp" not in hass.config.components


async def test_component_setup_with_validation_and_dependency(hass):
    """Test all config is passed to dependencies."""

    def config_check_setup(hass, config):
        """Test that config is passed in."""
        if config.get("comp_a", {}).get("valid", False):
            return True
        raise Exception(f"Config not passed in: {config}")

    platform = MockPlatform()

    mock_integration(hass, MockModule("comp_a", setup=config_check_setup))
    mock_integration(
        hass,
        MockModule("platform_a", setup=config_check_setup, dependencies=["comp_a"]),
    )

    mock_entity_platform(hass, "switch.platform_a", platform)

    await setup.async_setup_component(
        hass,
        "switch",
        {"comp_a": {"valid": True}, "switch": {"platform": "platform_a"}},
    )
    await hass.async_block_till_done()
    assert "comp_a" in hass.config.components


async def test_platform_specific_config_validation(hass):
    """Test platform that specifies config."""
    platform_schema = PLATFORM_SCHEMA.extend({"valid": True}, extra=vol.PREVENT_EXTRA)

    mock_setup = Mock(spec_set=True)

    mock_entity_platform(
        hass,
        "switch.platform_a",
        MockPlatform(platform_schema=platform_schema, setup_platform=mock_setup),
    )

    with assert_setup_component(0, "switch"):
        assert await setup.async_setup_component(
            hass,
            "switch",
            {"switch": {"platform": "platform_a", "invalid": True}},
        )
        await hass.async_block_till_done()
        assert mock_setup.call_count == 0

    hass.data.pop(setup.DATA_SETUP)
    hass.config.components.remove("switch")

    with assert_setup_component(0):
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

    hass.data.pop(setup.DATA_SETUP)
    hass.config.components.remove("switch")

    with assert_setup_component(1, "switch"):
        assert await setup.async_setup_component(
            hass,
            "switch",
            {"switch": {"platform": "platform_a", "valid": True}},
        )
        await hass.async_block_till_done()
        assert mock_setup.call_count == 1


async def test_disable_component_if_invalid_return(hass):
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


async def test_all_work_done_before_start(hass):
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


async def test_component_warn_slow_setup(hass):
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


async def test_platform_no_warn_slow(hass):
    """Do not warn for long entity setup time."""
    mock_integration(
        hass, MockModule("test_component1", platform_schema=PLATFORM_SCHEMA)
    )
    with patch.object(hass.loop, "call_later") as mock_call:
        result = await setup.async_setup_component(hass, "test_component1", {})
        assert result
        assert len(mock_call.mock_calls) == 0


async def test_platform_error_slow_setup(hass, caplog):
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
        assert "test_component1 is taking longer than 0.1 seconds" in caplog.text


async def test_when_setup_already_loaded(hass):
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


async def test_async_when_setup_or_start_already_loaded(hass):
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


async def test_setup_import_blows_up(hass):
    """Test that we handle it correctly when importing integration blows up."""
    with patch(
        "homeassistant.loader.Integration.get_component", side_effect=ImportError
    ):
        assert not await setup.async_setup_component(hass, "sun", {})


async def test_parallel_entry_setup(hass, mock_handlers):
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
    mock_entity_platform(hass, "config_flow.comp", None)
    await setup.async_setup_component(hass, "comp", {})

    assert calls == [1, 2, 1, 2]


async def test_integration_disabled(hass, caplog):
    """Test we can disable an integration."""
    disabled_reason = "Dependency contains code that breaks Home Assistant"
    mock_integration(
        hass,
        MockModule("test_component1", partial_manifest={"disabled": disabled_reason}),
    )
    result = await setup.async_setup_component(hass, "test_component1", {})
    assert not result
    assert disabled_reason in caplog.text


async def test_integration_logs_is_custom(hass, caplog):
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
    assert "Setup failed for custom integration test_component1: Boom" in caplog.text


async def test_async_get_loaded_integrations(hass):
    """Test we can enumerate loaded integations."""
    hass.config.components.add("notbase")
    hass.config.components.add("switch")
    hass.config.components.add("notbase.switch")
    hass.config.components.add("myintegration")
    hass.config.components.add("device_tracker")
    hass.config.components.add("device_tracker.other")
    hass.config.components.add("myintegration.light")
    assert setup.async_get_loaded_integrations(hass) == {
        "other",
        "switch",
        "notbase",
        "myintegration",
        "device_tracker",
    }


async def test_integration_no_setup(hass, caplog):
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


async def test_integration_only_setup_entry(hass):
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


async def test_async_start_setup(hass):
    """Test setup started context manager keeps track of setup times."""
    with setup.async_start_setup(hass, ["august"]):
        assert isinstance(
            hass.data[setup.DATA_SETUP_STARTED]["august"], datetime.datetime
        )
        with setup.async_start_setup(hass, ["august"]):
            assert isinstance(
                hass.data[setup.DATA_SETUP_STARTED]["august_2"], datetime.datetime
            )

    assert "august" not in hass.data[setup.DATA_SETUP_STARTED]
    assert isinstance(hass.data[setup.DATA_SETUP_TIME]["august"], datetime.timedelta)
    assert "august_2" not in hass.data[setup.DATA_SETUP_TIME]


async def test_async_start_setup_platforms(hass):
    """Test setup started context manager keeps track of setup times for platforms."""
    with setup.async_start_setup(hass, ["sensor.august"]):
        assert isinstance(
            hass.data[setup.DATA_SETUP_STARTED]["sensor.august"], datetime.datetime
        )

    assert "august" not in hass.data[setup.DATA_SETUP_STARTED]
    assert isinstance(hass.data[setup.DATA_SETUP_TIME]["august"], datetime.timedelta)
    assert "sensor" not in hass.data[setup.DATA_SETUP_TIME]
