"""Test component/platform setup."""
# pylint: disable=protected-access
import asyncio
import logging
import os
import threading

import pytest
import voluptuous as vol

from homeassistant import config_entries, setup
import homeassistant.config as config_util
from homeassistant.const import EVENT_COMPONENT_LOADED, EVENT_HOMEASSISTANT_START
from homeassistant.core import callback
from homeassistant.helpers import discovery
from homeassistant.helpers.config_validation import (
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
import homeassistant.util.dt as dt_util

from tests.async_mock import Mock, patch
from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    assert_setup_component,
    get_test_config_dir,
    get_test_home_assistant,
    mock_entity_platform,
    mock_integration,
)

ORIG_TIMEZONE = dt_util.DEFAULT_TIME_ZONE
VERSION_PATH = os.path.join(get_test_config_dir(), config_util.VERSION_FILE)

_LOGGER = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def mock_handlers():
    """Mock config flows."""

    class MockFlowHandler(config_entries.ConfigFlow):
        """Define a mock flow handler."""

        VERSION = 1

    with patch.dict(config_entries.HANDLERS, {"comp": MockFlowHandler}):
        yield


class TestSetup:
    """Test the bootstrap utils."""

    hass = None
    backup_cache = None

    # pylint: disable=invalid-name, no-self-use
    def setup_method(self, method):
        """Set up the test."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Clean up."""
        self.hass.stop()

    def test_validate_component_config(self):
        """Test validating component configuration."""
        config_schema = vol.Schema({"comp_conf": {"hello": str}}, required=True)
        mock_integration(
            self.hass, MockModule("comp_conf", config_schema=config_schema)
        )

        with assert_setup_component(0):
            assert not setup.setup_component(self.hass, "comp_conf", {})

        self.hass.data.pop(setup.DATA_SETUP)

        with assert_setup_component(0):
            assert not setup.setup_component(
                self.hass, "comp_conf", {"comp_conf": None}
            )

        self.hass.data.pop(setup.DATA_SETUP)

        with assert_setup_component(0):
            assert not setup.setup_component(self.hass, "comp_conf", {"comp_conf": {}})

        self.hass.data.pop(setup.DATA_SETUP)

        with assert_setup_component(0):
            assert not setup.setup_component(
                self.hass,
                "comp_conf",
                {"comp_conf": {"hello": "world", "invalid": "extra"}},
            )

        self.hass.data.pop(setup.DATA_SETUP)

        with assert_setup_component(1):
            assert setup.setup_component(
                self.hass, "comp_conf", {"comp_conf": {"hello": "world"}}
            )

    def test_validate_platform_config(self, caplog):
        """Test validating platform configuration."""
        platform_schema = PLATFORM_SCHEMA.extend({"hello": str})
        platform_schema_base = PLATFORM_SCHEMA_BASE.extend({})
        mock_integration(
            self.hass,
            MockModule("platform_conf", platform_schema_base=platform_schema_base),
        )
        mock_entity_platform(
            self.hass,
            "platform_conf.whatever",
            MockPlatform(platform_schema=platform_schema),
        )

        with assert_setup_component(0):
            assert setup.setup_component(
                self.hass,
                "platform_conf",
                {"platform_conf": {"platform": "not_existing", "hello": "world"}},
            )

        self.hass.data.pop(setup.DATA_SETUP)
        self.hass.config.components.remove("platform_conf")

        with assert_setup_component(1):
            assert setup.setup_component(
                self.hass,
                "platform_conf",
                {"platform_conf": {"platform": "whatever", "hello": "world"}},
            )

        self.hass.data.pop(setup.DATA_SETUP)
        self.hass.config.components.remove("platform_conf")

        with assert_setup_component(1):
            assert setup.setup_component(
                self.hass,
                "platform_conf",
                {"platform_conf": [{"platform": "whatever", "hello": "world"}]},
            )

        self.hass.data.pop(setup.DATA_SETUP)
        self.hass.config.components.remove("platform_conf")

        # Any falsey platform config will be ignored (None, {}, etc)
        with assert_setup_component(0) as config:
            assert setup.setup_component(
                self.hass, "platform_conf", {"platform_conf": None}
            )
            assert "platform_conf" in self.hass.config.components
            assert not config["platform_conf"]  # empty

            assert setup.setup_component(
                self.hass, "platform_conf", {"platform_conf": {}}
            )
            assert "platform_conf" in self.hass.config.components
            assert not config["platform_conf"]  # empty

    def test_validate_platform_config_2(self, caplog):
        """Test component PLATFORM_SCHEMA_BASE prio over PLATFORM_SCHEMA."""
        platform_schema = PLATFORM_SCHEMA.extend({"hello": str})
        platform_schema_base = PLATFORM_SCHEMA_BASE.extend({"hello": "world"})
        mock_integration(
            self.hass,
            MockModule(
                "platform_conf",
                platform_schema=platform_schema,
                platform_schema_base=platform_schema_base,
            ),
        )

        mock_entity_platform(
            self.hass,
            "platform_conf.whatever",
            MockPlatform("whatever", platform_schema=platform_schema),
        )

        with assert_setup_component(1):
            assert setup.setup_component(
                self.hass,
                "platform_conf",
                {
                    # pass
                    "platform_conf": {"platform": "whatever", "hello": "world"},
                    # fail: key hello violates component platform_schema_base
                    "platform_conf 2": {"platform": "whatever", "hello": "there"},
                },
            )

    def test_validate_platform_config_3(self, caplog):
        """Test fallback to component PLATFORM_SCHEMA."""
        component_schema = PLATFORM_SCHEMA_BASE.extend({"hello": str})
        platform_schema = PLATFORM_SCHEMA.extend({"cheers": str, "hello": "world"})
        mock_integration(
            self.hass, MockModule("platform_conf", platform_schema=component_schema)
        )

        mock_entity_platform(
            self.hass,
            "platform_conf.whatever",
            MockPlatform("whatever", platform_schema=platform_schema),
        )

        with assert_setup_component(1):
            assert setup.setup_component(
                self.hass,
                "platform_conf",
                {
                    # pass
                    "platform_conf": {"platform": "whatever", "hello": "world"},
                    # fail: key hello violates component platform_schema
                    "platform_conf 2": {"platform": "whatever", "hello": "there"},
                },
            )

    def test_validate_platform_config_4(self):
        """Test entity_namespace in PLATFORM_SCHEMA."""
        component_schema = PLATFORM_SCHEMA_BASE
        platform_schema = PLATFORM_SCHEMA
        mock_integration(
            self.hass,
            MockModule("platform_conf", platform_schema_base=component_schema),
        )

        mock_entity_platform(
            self.hass,
            "platform_conf.whatever",
            MockPlatform(platform_schema=platform_schema),
        )

        with assert_setup_component(1):
            assert setup.setup_component(
                self.hass,
                "platform_conf",
                {
                    "platform_conf": {
                        # pass: entity_namespace accepted by PLATFORM_SCHEMA
                        "platform": "whatever",
                        "entity_namespace": "yummy",
                    }
                },
            )

        self.hass.data.pop(setup.DATA_SETUP)
        self.hass.config.components.remove("platform_conf")

    def test_component_not_found(self):
        """setup_component should not crash if component doesn't exist."""
        assert setup.setup_component(self.hass, "non_existing", {}) is False

    def test_component_not_double_initialized(self):
        """Test we do not set up a component twice."""
        mock_setup = Mock(return_value=True)

        mock_integration(self.hass, MockModule("comp", setup=mock_setup))

        assert setup.setup_component(self.hass, "comp", {})
        assert mock_setup.called

        mock_setup.reset_mock()

        assert setup.setup_component(self.hass, "comp", {})
        assert not mock_setup.called

    @patch("homeassistant.util.package.install_package", return_value=False)
    def test_component_not_installed_if_requirement_fails(self, mock_install):
        """Component setup should fail if requirement can't install."""
        self.hass.config.skip_pip = False
        mock_integration(self.hass, MockModule("comp", requirements=["package==0.0.1"]))

        assert not setup.setup_component(self.hass, "comp", {})
        assert "comp" not in self.hass.config.components

    def test_component_not_setup_twice_if_loaded_during_other_setup(self):
        """Test component setup while waiting for lock is not set up twice."""
        result = []

        async def async_setup(hass, config):
            """Tracking Setup."""
            result.append(1)

        mock_integration(self.hass, MockModule("comp", async_setup=async_setup))

        def setup_component():
            """Set up the component."""
            setup.setup_component(self.hass, "comp", {})

        thread = threading.Thread(target=setup_component)
        thread.start()
        setup.setup_component(self.hass, "comp", {})

        thread.join()

        assert len(result) == 1

    def test_component_not_setup_missing_dependencies(self):
        """Test we do not set up a component if not all dependencies loaded."""
        deps = ["maybe_existing"]
        mock_integration(self.hass, MockModule("comp", dependencies=deps))

        assert not setup.setup_component(self.hass, "comp", {})
        assert "comp" not in self.hass.config.components

        self.hass.data.pop(setup.DATA_SETUP)

        mock_integration(self.hass, MockModule("comp2", dependencies=deps))
        mock_integration(self.hass, MockModule("maybe_existing"))

        assert setup.setup_component(self.hass, "comp2", {})

    def test_component_failing_setup(self):
        """Test component that fails setup."""
        mock_integration(
            self.hass, MockModule("comp", setup=lambda hass, config: False)
        )

        assert not setup.setup_component(self.hass, "comp", {})
        assert "comp" not in self.hass.config.components

    def test_component_exception_setup(self):
        """Test component that raises exception during setup."""

        def exception_setup(hass, config):
            """Raise exception."""
            raise Exception("fail!")

        mock_integration(self.hass, MockModule("comp", setup=exception_setup))

        assert not setup.setup_component(self.hass, "comp", {})
        assert "comp" not in self.hass.config.components

    def test_component_setup_with_validation_and_dependency(self):
        """Test all config is passed to dependencies."""

        def config_check_setup(hass, config):
            """Test that config is passed in."""
            if config.get("comp_a", {}).get("valid", False):
                return True
            raise Exception(f"Config not passed in: {config}")

        platform = MockPlatform()

        mock_integration(self.hass, MockModule("comp_a", setup=config_check_setup))
        mock_integration(
            self.hass,
            MockModule("platform_a", setup=config_check_setup, dependencies=["comp_a"]),
        )

        mock_entity_platform(self.hass, "switch.platform_a", platform)

        setup.setup_component(
            self.hass,
            "switch",
            {"comp_a": {"valid": True}, "switch": {"platform": "platform_a"}},
        )
        self.hass.block_till_done()
        assert "comp_a" in self.hass.config.components

    def test_platform_specific_config_validation(self):
        """Test platform that specifies config."""
        platform_schema = PLATFORM_SCHEMA.extend(
            {"valid": True}, extra=vol.PREVENT_EXTRA
        )

        mock_setup = Mock(spec_set=True)

        mock_entity_platform(
            self.hass,
            "switch.platform_a",
            MockPlatform(platform_schema=platform_schema, setup_platform=mock_setup),
        )

        with assert_setup_component(0, "switch"):
            assert setup.setup_component(
                self.hass,
                "switch",
                {"switch": {"platform": "platform_a", "invalid": True}},
            )
            self.hass.block_till_done()
            assert mock_setup.call_count == 0

        self.hass.data.pop(setup.DATA_SETUP)
        self.hass.config.components.remove("switch")

        with assert_setup_component(0):
            assert setup.setup_component(
                self.hass,
                "switch",
                {
                    "switch": {
                        "platform": "platform_a",
                        "valid": True,
                        "invalid_extra": True,
                    }
                },
            )
            self.hass.block_till_done()
            assert mock_setup.call_count == 0

        self.hass.data.pop(setup.DATA_SETUP)
        self.hass.config.components.remove("switch")

        with assert_setup_component(1, "switch"):
            assert setup.setup_component(
                self.hass,
                "switch",
                {"switch": {"platform": "platform_a", "valid": True}},
            )
            self.hass.block_till_done()
            assert mock_setup.call_count == 1

    def test_disable_component_if_invalid_return(self):
        """Test disabling component if invalid return."""
        mock_integration(
            self.hass, MockModule("disabled_component", setup=lambda hass, config: None)
        )

        assert not setup.setup_component(self.hass, "disabled_component", {})
        assert "disabled_component" not in self.hass.config.components

        self.hass.data.pop(setup.DATA_SETUP)
        mock_integration(
            self.hass,
            MockModule("disabled_component", setup=lambda hass, config: False),
        )

        assert not setup.setup_component(self.hass, "disabled_component", {})
        assert "disabled_component" not in self.hass.config.components

        self.hass.data.pop(setup.DATA_SETUP)
        mock_integration(
            self.hass, MockModule("disabled_component", setup=lambda hass, config: True)
        )

        assert setup.setup_component(self.hass, "disabled_component", {})
        assert "disabled_component" in self.hass.config.components

    def test_all_work_done_before_start(self):
        """Test all init work done till start."""
        call_order = []

        def component1_setup(hass, config):
            """Set up mock component."""
            discovery.discover(hass, "test_component2", {}, "test_component2", {})
            discovery.discover(hass, "test_component3", {}, "test_component3", {})
            return True

        def component_track_setup(hass, config):
            """Set up mock component."""
            call_order.append(1)
            return True

        mock_integration(
            self.hass, MockModule("test_component1", setup=component1_setup)
        )

        mock_integration(
            self.hass, MockModule("test_component2", setup=component_track_setup)
        )

        mock_integration(
            self.hass, MockModule("test_component3", setup=component_track_setup)
        )

        @callback
        def track_start(event):
            """Track start event."""
            call_order.append(2)

        self.hass.bus.listen_once(EVENT_HOMEASSISTANT_START, track_start)

        self.hass.add_job(setup.async_setup_component(self.hass, "test_component1", {}))
        self.hass.block_till_done()
        self.hass.start()
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

    with patch.object(setup, "SLOW_SETUP_MAX_WAIT", 1):
        called = []

        async def async_setup(*args):
            """Tracking Setup."""
            called.append(1)
            await asyncio.sleep(2)

        mock_integration(hass, MockModule("test_component1", async_setup=async_setup))
        result = await setup.async_setup_component(hass, "test_component1", {})
        assert len(called) == 1
        assert not result
        assert "test_component1 is taking longer than 1 seconds" in caplog.text


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


async def test_setup_import_blows_up(hass):
    """Test that we handle it correctly when importing integration blows up."""
    with patch(
        "homeassistant.loader.Integration.get_component", side_effect=ValueError
    ):
        assert not await setup.async_setup_component(hass, "sun", {})


async def test_parallel_entry_setup(hass):
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
        hass, MockModule("comp", async_setup_entry=mock_async_setup_entry,),
    )
    mock_entity_platform(hass, "config_flow.comp", None)
    await setup.async_setup_component(hass, "comp", {})

    assert calls == [1, 2, 1, 2]
