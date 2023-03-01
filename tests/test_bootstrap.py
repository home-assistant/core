"""Test the bootstrapping."""

import asyncio
import glob
import os
from unittest.mock import Mock, patch

import pytest

from homeassistant import bootstrap, runner
import homeassistant.config as config_util
from homeassistant.const import SIGNAL_BOOTSTRAP_INTEGRATIONS
from homeassistant.core import HomeAssistant, async_get_hass, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .common import (
    MockModule,
    MockPlatform,
    get_test_config_dir,
    mock_coro,
    mock_entity_platform,
    mock_integration,
)

VERSION_PATH = os.path.join(get_test_config_dir(), config_util.VERSION_FILE)


@pytest.fixture(autouse=True)
def apply_mock_storage(hass_storage):
    """Apply the storage mock."""


@pytest.fixture(autouse=True)
async def apply_stop_hass(stop_hass: None) -> None:
    """Make sure all hass are stopped."""


@pytest.fixture(autouse=True)
def mock_http_start_stop():
    """Mock HTTP start and stop."""
    with patch(
        "homeassistant.components.http.start_http_server_and_save_config"
    ), patch("homeassistant.components.http.HomeAssistantHTTP.stop"):
        yield


@patch("homeassistant.bootstrap.async_enable_logging", Mock())
async def test_home_assistant_core_config_validation(hass: HomeAssistant) -> None:
    """Test if we pass in wrong information for HA conf."""
    # Extensive HA conf validation testing is done
    result = await bootstrap.async_from_config_dict(
        {"homeassistant": {"latitude": "some string"}}, hass
    )
    assert result is None


async def test_async_enable_logging(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test to ensure logging is migrated to the queue handlers."""
    with patch("logging.getLogger"), patch(
        "homeassistant.bootstrap.async_activate_log_queue_handler"
    ) as mock_async_activate_log_queue_handler, patch(
        "homeassistant.bootstrap.logging.handlers.RotatingFileHandler.doRollover",
        side_effect=OSError,
    ):
        bootstrap.async_enable_logging(hass)
        mock_async_activate_log_queue_handler.assert_called_once()
        mock_async_activate_log_queue_handler.reset_mock()
        bootstrap.async_enable_logging(
            hass,
            log_rotate_days=5,
            log_file="test.log",
        )
        mock_async_activate_log_queue_handler.assert_called_once()
        for f in glob.glob("test.log*"):
            os.remove(f)
        for f in glob.glob("testing_config/home-assistant.log*"):
            os.remove(f)

    assert "Error rolling over log file" in caplog.text


async def test_load_hassio(hass: HomeAssistant) -> None:
    """Test that we load Hass.io component."""
    with patch.dict(os.environ, {}, clear=True):
        assert bootstrap._get_domains(hass, {}) == set()

    with patch.dict(os.environ, {"SUPERVISOR": "1"}):
        assert bootstrap._get_domains(hass, {}) == {"hassio"}


@pytest.mark.parametrize("load_registries", [False])
async def test_empty_setup(hass: HomeAssistant) -> None:
    """Test an empty set up loads the core."""
    await bootstrap.async_from_config_dict({}, hass)
    for domain in bootstrap.CORE_INTEGRATIONS:
        assert domain in hass.config.components, domain


async def test_core_failure_loads_safe_mode(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test failing core setup aborts further setup."""
    with patch(
        "homeassistant.components.homeassistant.async_setup",
        return_value=mock_coro(False),
    ):
        await bootstrap.async_from_config_dict({"group": {}}, hass)

    assert "core failed to initialize" in caplog.text
    # We aborted early, group not set up
    assert "group" not in hass.config.components


@pytest.mark.parametrize("load_registries", [False])
async def test_setting_up_config(hass: HomeAssistant) -> None:
    """Test we set up domains in config."""
    await bootstrap._async_set_up_integrations(
        hass, {"group hello": {}, "homeassistant": {}}
    )

    assert "group" in hass.config.components


@pytest.mark.parametrize("load_registries", [False])
async def test_setup_after_deps_all_present(hass: HomeAssistant) -> None:
    """Test after_dependencies when all present."""
    order = []

    def gen_domain_setup(domain):
        async def async_setup(hass, config):
            order.append(domain)
            return True

        return async_setup

    mock_integration(
        hass, MockModule(domain="root", async_setup=gen_domain_setup("root"))
    )
    mock_integration(
        hass,
        MockModule(
            domain="first_dep",
            async_setup=gen_domain_setup("first_dep"),
            partial_manifest={"after_dependencies": ["root"]},
        ),
    )
    mock_integration(
        hass,
        MockModule(
            domain="second_dep",
            async_setup=gen_domain_setup("second_dep"),
            partial_manifest={"after_dependencies": ["first_dep"]},
        ),
    )

    with patch(
        "homeassistant.components.logger.async_setup", gen_domain_setup("logger")
    ):
        await bootstrap._async_set_up_integrations(
            hass, {"root": {}, "first_dep": {}, "second_dep": {}, "logger": {}}
        )

    assert "root" in hass.config.components
    assert "first_dep" in hass.config.components
    assert "second_dep" in hass.config.components
    assert order == ["logger", "root", "first_dep", "second_dep"]


@pytest.mark.parametrize("load_registries", [False])
async def test_setup_after_deps_in_stage_1_ignored(hass: HomeAssistant) -> None:
    """Test after_dependencies are ignored in stage 1."""
    # This test relies on this
    assert "cloud" in bootstrap.STAGE_1_INTEGRATIONS
    order = []

    def gen_domain_setup(domain):
        async def async_setup(hass, config):
            order.append(domain)
            return True

        return async_setup

    mock_integration(
        hass,
        MockModule(
            domain="normal_integration",
            async_setup=gen_domain_setup("normal_integration"),
            partial_manifest={"after_dependencies": ["an_after_dep"]},
        ),
    )
    mock_integration(
        hass,
        MockModule(
            domain="an_after_dep",
            async_setup=gen_domain_setup("an_after_dep"),
        ),
    )
    mock_integration(
        hass,
        MockModule(
            domain="cloud",
            async_setup=gen_domain_setup("cloud"),
            partial_manifest={"after_dependencies": ["normal_integration"]},
        ),
    )

    await bootstrap._async_set_up_integrations(
        hass, {"cloud": {}, "normal_integration": {}, "an_after_dep": {}}
    )

    assert "normal_integration" in hass.config.components
    assert "cloud" in hass.config.components
    assert order == ["cloud", "an_after_dep", "normal_integration"]


@pytest.mark.parametrize("load_registries", [False])
async def test_setup_frontend_before_recorder(hass: HomeAssistant) -> None:
    """Test frontend is setup before recorder."""
    order = []

    def gen_domain_setup(domain):
        async def async_setup(hass, config):
            order.append(domain)
            return True

        return async_setup

    mock_integration(
        hass,
        MockModule(
            domain="normal_integration",
            async_setup=gen_domain_setup("normal_integration"),
            partial_manifest={"after_dependencies": ["an_after_dep"]},
        ),
    )
    mock_integration(
        hass,
        MockModule(
            domain="an_after_dep",
            async_setup=gen_domain_setup("an_after_dep"),
        ),
    )
    mock_integration(
        hass,
        MockModule(
            domain="frontend",
            async_setup=gen_domain_setup("frontend"),
            partial_manifest={
                "dependencies": ["http"],
                "after_dependencies": ["an_after_dep"],
            },
        ),
    )
    mock_integration(
        hass,
        MockModule(
            domain="http",
            async_setup=gen_domain_setup("http"),
        ),
    )
    mock_integration(
        hass,
        MockModule(
            domain="recorder",
            async_setup=gen_domain_setup("recorder"),
        ),
    )

    await bootstrap._async_set_up_integrations(
        hass,
        {
            "frontend": {},
            "http": {},
            "recorder": {},
            "normal_integration": {},
            "an_after_dep": {},
        },
    )

    assert "frontend" in hass.config.components
    assert "normal_integration" in hass.config.components
    assert "recorder" in hass.config.components
    assert order == [
        "http",
        "frontend",
        "recorder",
        "an_after_dep",
        "normal_integration",
    ]


@pytest.mark.parametrize("load_registries", [False])
async def test_setup_after_deps_via_platform(hass: HomeAssistant) -> None:
    """Test after_dependencies set up via platform."""
    order = []
    after_dep_event = asyncio.Event()

    def gen_domain_setup(domain):
        async def async_setup(hass, config):
            if domain == "after_dep_of_platform_int":
                await after_dep_event.wait()

            order.append(domain)
            return True

        return async_setup

    mock_integration(
        hass,
        MockModule(
            domain="after_dep_of_platform_int",
            async_setup=gen_domain_setup("after_dep_of_platform_int"),
        ),
    )
    mock_integration(
        hass,
        MockModule(
            domain="platform_int",
            async_setup=gen_domain_setup("platform_int"),
            partial_manifest={"after_dependencies": ["after_dep_of_platform_int"]},
        ),
    )
    mock_entity_platform(hass, "light.platform_int", MockPlatform())

    @callback
    def continue_loading(_):
        """When light component loaded, continue other loading."""
        after_dep_event.set()

    hass.bus.async_listen_once("component_loaded", continue_loading)

    await bootstrap._async_set_up_integrations(
        hass, {"light": {"platform": "platform_int"}, "after_dep_of_platform_int": {}}
    )

    assert "light" in hass.config.components
    assert "after_dep_of_platform_int" in hass.config.components
    assert "platform_int" in hass.config.components
    assert order == ["after_dep_of_platform_int", "platform_int"]


@pytest.mark.parametrize("load_registries", [False])
async def test_setup_after_deps_not_trigger_load(hass: HomeAssistant) -> None:
    """Test after_dependencies does not trigger loading it."""
    order = []

    def gen_domain_setup(domain):
        async def async_setup(hass, config):
            order.append(domain)
            return True

        return async_setup

    mock_integration(
        hass, MockModule(domain="root", async_setup=gen_domain_setup("root"))
    )
    mock_integration(
        hass,
        MockModule(
            domain="first_dep",
            async_setup=gen_domain_setup("first_dep"),
            partial_manifest={"after_dependencies": ["root"]},
        ),
    )
    mock_integration(
        hass,
        MockModule(
            domain="second_dep",
            async_setup=gen_domain_setup("second_dep"),
            partial_manifest={"after_dependencies": ["first_dep"]},
        ),
    )

    await bootstrap._async_set_up_integrations(hass, {"root": {}, "second_dep": {}})

    assert "root" in hass.config.components
    assert "first_dep" not in hass.config.components
    assert "second_dep" in hass.config.components


@pytest.mark.parametrize("load_registries", [False])
async def test_setup_after_deps_not_present(hass: HomeAssistant) -> None:
    """Test after_dependencies when referenced integration doesn't exist."""
    order = []

    def gen_domain_setup(domain):
        async def async_setup(hass, config):
            order.append(domain)
            return True

        return async_setup

    mock_integration(
        hass, MockModule(domain="root", async_setup=gen_domain_setup("root"))
    )
    mock_integration(
        hass,
        MockModule(
            domain="second_dep",
            async_setup=gen_domain_setup("second_dep"),
            partial_manifest={"after_dependencies": ["first_dep"]},
        ),
    )

    await bootstrap._async_set_up_integrations(
        hass, {"root": {}, "first_dep": {}, "second_dep": {}}
    )

    assert "root" in hass.config.components
    assert "first_dep" not in hass.config.components
    assert "second_dep" in hass.config.components
    assert order == ["root", "second_dep"]


@pytest.fixture
def mock_is_virtual_env():
    """Mock enable logging."""
    with patch(
        "homeassistant.bootstrap.is_virtual_env", return_value=False
    ) as is_virtual_env:
        yield is_virtual_env


@pytest.fixture
def mock_enable_logging():
    """Mock enable logging."""
    with patch("homeassistant.bootstrap.async_enable_logging") as enable_logging:
        yield enable_logging


@pytest.fixture
def mock_mount_local_lib_path():
    """Mock enable logging."""
    with patch(
        "homeassistant.bootstrap.async_mount_local_lib_path"
    ) as mount_local_lib_path:
        yield mount_local_lib_path


@pytest.fixture
def mock_process_ha_config_upgrade():
    """Mock enable logging."""
    with patch(
        "homeassistant.config.process_ha_config_upgrade"
    ) as process_ha_config_upgrade:
        yield process_ha_config_upgrade


@pytest.fixture
def mock_ensure_config_exists():
    """Mock enable logging."""
    with patch(
        "homeassistant.config.async_ensure_config_exists", return_value=True
    ) as ensure_config_exists:
        yield ensure_config_exists


@pytest.mark.parametrize("hass_config", [{"browser": {}, "frontend": {}}])
async def test_setup_hass(
    mock_hass_config: None,
    mock_enable_logging,
    mock_is_virtual_env,
    mock_mount_local_lib_path,
    mock_ensure_config_exists,
    mock_process_ha_config_upgrade,
    caplog: pytest.LogCaptureFixture,
    event_loop,
) -> None:
    """Test it works."""
    verbose = Mock()
    log_rotate_days = Mock()
    log_file = Mock()
    log_no_color = Mock()

    with patch.object(bootstrap, "LOG_SLOW_STARTUP_INTERVAL", 5000):
        hass = await bootstrap.async_setup_hass(
            runner.RuntimeConfig(
                config_dir=get_test_config_dir(),
                verbose=verbose,
                log_rotate_days=log_rotate_days,
                log_file=log_file,
                log_no_color=log_no_color,
                skip_pip=True,
                safe_mode=False,
            ),
        )

    assert "Waiting on integrations to complete setup" not in caplog.text

    assert "browser" in hass.config.components
    assert "safe_mode" not in hass.config.components

    assert len(mock_enable_logging.mock_calls) == 1
    assert mock_enable_logging.mock_calls[0][1] == (
        hass,
        verbose,
        log_rotate_days,
        log_file,
        log_no_color,
    )
    assert len(mock_mount_local_lib_path.mock_calls) == 1
    assert len(mock_ensure_config_exists.mock_calls) == 1
    assert len(mock_process_ha_config_upgrade.mock_calls) == 1

    assert hass == async_get_hass()


@pytest.mark.parametrize("hass_config", [{"browser": {}, "frontend": {}}])
async def test_setup_hass_takes_longer_than_log_slow_startup(
    mock_hass_config: None,
    mock_enable_logging,
    mock_is_virtual_env,
    mock_mount_local_lib_path,
    mock_ensure_config_exists,
    mock_process_ha_config_upgrade,
    caplog: pytest.LogCaptureFixture,
    event_loop,
) -> None:
    """Test it works."""
    verbose = Mock()
    log_rotate_days = Mock()
    log_file = Mock()
    log_no_color = Mock()

    async def _async_setup_that_blocks_startup(*args, **kwargs):
        await asyncio.sleep(0.6)
        return True

    with patch.object(bootstrap, "LOG_SLOW_STARTUP_INTERVAL", 0.3), patch.object(
        bootstrap, "SLOW_STARTUP_CHECK_INTERVAL", 0.05
    ), patch(
        "homeassistant.components.frontend.async_setup",
        side_effect=_async_setup_that_blocks_startup,
    ):
        await bootstrap.async_setup_hass(
            runner.RuntimeConfig(
                config_dir=get_test_config_dir(),
                verbose=verbose,
                log_rotate_days=log_rotate_days,
                log_file=log_file,
                log_no_color=log_no_color,
                skip_pip=True,
                safe_mode=False,
            ),
        )

    assert "Waiting on integrations to complete setup" in caplog.text


async def test_setup_hass_invalid_yaml(
    mock_enable_logging,
    mock_is_virtual_env,
    mock_mount_local_lib_path,
    mock_ensure_config_exists,
    mock_process_ha_config_upgrade,
    event_loop,
) -> None:
    """Test it works."""
    with patch(
        "homeassistant.config.async_hass_config_yaml", side_effect=HomeAssistantError
    ):
        hass = await bootstrap.async_setup_hass(
            runner.RuntimeConfig(
                config_dir=get_test_config_dir(),
                verbose=False,
                log_rotate_days=10,
                log_file="",
                log_no_color=False,
                skip_pip=True,
                safe_mode=False,
            ),
        )

    assert "safe_mode" in hass.config.components
    assert len(mock_mount_local_lib_path.mock_calls) == 0


async def test_setup_hass_config_dir_nonexistent(
    mock_enable_logging,
    mock_is_virtual_env,
    mock_mount_local_lib_path,
    mock_ensure_config_exists,
    mock_process_ha_config_upgrade,
    event_loop,
) -> None:
    """Test it works."""
    mock_ensure_config_exists.return_value = False

    assert (
        await bootstrap.async_setup_hass(
            runner.RuntimeConfig(
                config_dir=get_test_config_dir(),
                verbose=False,
                log_rotate_days=10,
                log_file="",
                log_no_color=False,
                skip_pip=True,
                safe_mode=False,
            ),
        )
        is None
    )


async def test_setup_hass_safe_mode(
    mock_enable_logging,
    mock_is_virtual_env,
    mock_mount_local_lib_path,
    mock_ensure_config_exists,
    mock_process_ha_config_upgrade,
    event_loop,
) -> None:
    """Test it works."""
    with patch("homeassistant.components.browser.setup") as browser_setup, patch(
        "homeassistant.config_entries.ConfigEntries.async_domains",
        return_value=["browser"],
    ):
        hass = await bootstrap.async_setup_hass(
            runner.RuntimeConfig(
                config_dir=get_test_config_dir(),
                verbose=False,
                log_rotate_days=10,
                log_file="",
                log_no_color=False,
                skip_pip=True,
                safe_mode=True,
            ),
        )

    assert "safe_mode" in hass.config.components
    assert len(mock_mount_local_lib_path.mock_calls) == 0

    # Validate we didn't try to set up config entry.
    assert "browser" not in hass.config.components
    assert len(browser_setup.mock_calls) == 0


@pytest.mark.parametrize("hass_config", [{"homeassistant": {"non-existing": 1}}])
async def test_setup_hass_invalid_core_config(
    mock_hass_config: None,
    mock_enable_logging,
    mock_is_virtual_env,
    mock_mount_local_lib_path,
    mock_ensure_config_exists,
    mock_process_ha_config_upgrade,
    event_loop,
) -> None:
    """Test it works."""
    hass = await bootstrap.async_setup_hass(
        runner.RuntimeConfig(
            config_dir=get_test_config_dir(),
            verbose=False,
            log_rotate_days=10,
            log_file="",
            log_no_color=False,
            skip_pip=True,
            safe_mode=False,
        ),
    )

    assert "safe_mode" in hass.config.components


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            "homeassistant": {
                "internal_url": "http://192.168.1.100:8123",
                "external_url": "https://abcdef.ui.nabu.casa",
            },
            "map": {},
            "person": {"invalid": True},
        }
    ],
)
async def test_setup_safe_mode_if_no_frontend(
    mock_hass_config: None,
    mock_enable_logging,
    mock_is_virtual_env,
    mock_mount_local_lib_path,
    mock_ensure_config_exists,
    mock_process_ha_config_upgrade,
    event_loop,
) -> None:
    """Test we setup safe mode if frontend didn't load."""
    verbose = Mock()
    log_rotate_days = Mock()
    log_file = Mock()
    log_no_color = Mock()

    hass = await bootstrap.async_setup_hass(
        runner.RuntimeConfig(
            config_dir=get_test_config_dir(),
            verbose=verbose,
            log_rotate_days=log_rotate_days,
            log_file=log_file,
            log_no_color=log_no_color,
            skip_pip=True,
            safe_mode=False,
        ),
    )

    assert "safe_mode" in hass.config.components
    assert hass.config.config_dir == get_test_config_dir()
    assert hass.config.skip_pip
    assert hass.config.internal_url == "http://192.168.1.100:8123"
    assert hass.config.external_url == "https://abcdef.ui.nabu.casa"


@pytest.mark.parametrize("load_registries", [False])
async def test_empty_integrations_list_is_only_sent_at_the_end_of_bootstrap(
    hass: HomeAssistant,
) -> None:
    """Test empty integrations list is only sent at the end of bootstrap."""
    order = []

    def gen_domain_setup(domain):
        async def async_setup(hass, config):
            order.append(domain)
            await asyncio.sleep(0.1)

            async def _background_task():
                await asyncio.sleep(0.2)

            await hass.async_create_task(_background_task())
            return True

        return async_setup

    mock_integration(
        hass,
        MockModule(
            domain="normal_integration",
            async_setup=gen_domain_setup("normal_integration"),
            partial_manifest={"after_dependencies": ["an_after_dep"]},
        ),
    )
    mock_integration(
        hass,
        MockModule(
            domain="an_after_dep",
            async_setup=gen_domain_setup("an_after_dep"),
        ),
    )

    integrations = []

    @callback
    def _bootstrap_integrations(data):
        integrations.append(data)

    async_dispatcher_connect(
        hass, SIGNAL_BOOTSTRAP_INTEGRATIONS, _bootstrap_integrations
    )
    with patch.object(bootstrap, "SLOW_STARTUP_CHECK_INTERVAL", 0.05):
        await bootstrap._async_set_up_integrations(
            hass, {"normal_integration": {}, "an_after_dep": {}}
        )
        await hass.async_block_till_done()

    assert integrations[0] != {}
    assert "an_after_dep" in integrations[0]
    assert integrations[-3] != {}
    assert integrations[-1] == {}

    assert "normal_integration" in hass.config.components
    assert order == ["an_after_dep", "normal_integration"]


@pytest.mark.parametrize("load_registries", [False])
async def test_warning_logged_on_wrap_up_timeout(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we log a warning on bootstrap timeout."""

    def gen_domain_setup(domain):
        async def async_setup(hass, config):
            async def _background_task():
                await asyncio.sleep(0.2)

            hass.async_create_task(_background_task())
            return True

        return async_setup

    mock_integration(
        hass,
        MockModule(
            domain="normal_integration",
            async_setup=gen_domain_setup("normal_integration"),
            partial_manifest={},
        ),
    )

    with patch.object(bootstrap, "WRAP_UP_TIMEOUT", 0):
        await bootstrap._async_set_up_integrations(hass, {"normal_integration": {}})
        await hass.async_block_till_done()

    assert "Setup timed out for bootstrap - moving forward" in caplog.text
