"""Test the bootstrapping."""
# pylint: disable=protected-access
import asyncio
import logging
import os
from unittest.mock import Mock

import pytest

from homeassistant import bootstrap
import homeassistant.config as config_util
from homeassistant.exceptions import HomeAssistantError
import homeassistant.util.dt as dt_util

from tests.async_mock import patch
from tests.common import (
    MockConfigEntry,
    MockModule,
    flush_store,
    get_test_config_dir,
    mock_coro,
    mock_integration,
)

ORIG_TIMEZONE = dt_util.DEFAULT_TIME_ZONE
VERSION_PATH = os.path.join(get_test_config_dir(), config_util.VERSION_FILE)

_LOGGER = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def apply_mock_storage(hass_storage):
    """Apply the storage mock."""


@patch("homeassistant.bootstrap.async_enable_logging", Mock())
async def test_home_assistant_core_config_validation(hass):
    """Test if we pass in wrong information for HA conf."""
    # Extensive HA conf validation testing is done
    result = await bootstrap.async_from_config_dict(
        {"homeassistant": {"latitude": "some string"}}, hass
    )
    assert result is None


async def test_async_enable_logging(hass):
    """Test to ensure logging is migrated to the queue handlers."""
    with patch("logging.getLogger"), patch(
        "homeassistant.bootstrap.async_activate_log_queue_handler"
    ) as mock_async_activate_log_queue_handler:
        bootstrap.async_enable_logging(hass)
        mock_async_activate_log_queue_handler.assert_called_once()


async def test_load_hassio(hass):
    """Test that we load Hass.io component."""
    with patch.dict(os.environ, {}, clear=True):
        assert bootstrap._get_domains(hass, {}) == set()

    with patch.dict(os.environ, {"HASSIO": "1"}):
        assert bootstrap._get_domains(hass, {}) == {"hassio"}


async def test_empty_setup(hass):
    """Test an empty set up loads the core."""
    await bootstrap.async_from_config_dict({}, hass)
    for domain in bootstrap.CORE_INTEGRATIONS:
        assert domain in hass.config.components, domain


async def test_core_failure_loads_safe_mode(hass, caplog):
    """Test failing core setup aborts further setup."""
    with patch(
        "homeassistant.components.homeassistant.async_setup",
        return_value=mock_coro(False),
    ):
        await bootstrap.async_from_config_dict({"group": {}}, hass)

    assert "core failed to initialize" in caplog.text
    # We aborted early, group not set up
    assert "group" not in hass.config.components


async def test_setting_up_config(hass, caplog):
    """Test we set up domains in config."""
    await bootstrap._async_set_up_integrations(
        hass, {"group hello": {}, "homeassistant": {}}
    )

    assert "group" in hass.config.components


async def test_setup_after_deps_all_present(hass, caplog):
    """Test after_dependencies when all present."""
    caplog.set_level(logging.DEBUG)
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

    await bootstrap._async_set_up_integrations(
        hass, {"root": {}, "first_dep": {}, "second_dep": {}}
    )

    assert "root" in hass.config.components
    assert "first_dep" in hass.config.components
    assert "second_dep" in hass.config.components
    assert order == ["root", "first_dep", "second_dep"]


async def test_setup_after_deps_not_trigger_load(hass, caplog):
    """Test after_dependencies does not trigger loading it."""
    caplog.set_level(logging.DEBUG)
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
    assert order == ["root", "second_dep"]


async def test_setup_after_deps_not_present(hass, caplog):
    """Test after_dependencies when referenced integration doesn't exist."""
    caplog.set_level(logging.DEBUG)
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


async def test_setup_hass(
    mock_enable_logging,
    mock_is_virtual_env,
    mock_mount_local_lib_path,
    mock_ensure_config_exists,
    mock_process_ha_config_upgrade,
    caplog,
):
    """Test it works."""
    verbose = Mock()
    log_rotate_days = Mock()
    log_file = Mock()
    log_no_color = Mock()

    with patch(
        "homeassistant.config.async_hass_config_yaml",
        return_value={"browser": {}, "frontend": {}},
    ), patch.object(bootstrap, "LOG_SLOW_STARTUP_INTERVAL", 5000), patch(
        "homeassistant.components.http.start_http_server_and_save_config"
    ):
        hass = await bootstrap.async_setup_hass(
            config_dir=get_test_config_dir(),
            verbose=verbose,
            log_rotate_days=log_rotate_days,
            log_file=log_file,
            log_no_color=log_no_color,
            skip_pip=True,
            safe_mode=False,
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


async def test_setup_hass_takes_longer_than_log_slow_startup(
    mock_enable_logging,
    mock_is_virtual_env,
    mock_mount_local_lib_path,
    mock_ensure_config_exists,
    mock_process_ha_config_upgrade,
    caplog,
):
    """Test it works."""
    verbose = Mock()
    log_rotate_days = Mock()
    log_file = Mock()
    log_no_color = Mock()

    async def _async_setup_that_blocks_startup(*args, **kwargs):
        await asyncio.sleep(0.6)
        return True

    with patch(
        "homeassistant.config.async_hass_config_yaml",
        return_value={"browser": {}, "frontend": {}},
    ), patch.object(bootstrap, "LOG_SLOW_STARTUP_INTERVAL", 0.3), patch(
        "homeassistant.components.frontend.async_setup",
        side_effect=_async_setup_that_blocks_startup,
    ), patch(
        "homeassistant.components.http.start_http_server_and_save_config"
    ):
        await bootstrap.async_setup_hass(
            config_dir=get_test_config_dir(),
            verbose=verbose,
            log_rotate_days=log_rotate_days,
            log_file=log_file,
            log_no_color=log_no_color,
            skip_pip=True,
            safe_mode=False,
        )

    assert "Waiting on integrations to complete setup" in caplog.text


async def test_setup_hass_invalid_yaml(
    mock_enable_logging,
    mock_is_virtual_env,
    mock_mount_local_lib_path,
    mock_ensure_config_exists,
    mock_process_ha_config_upgrade,
):
    """Test it works."""
    with patch(
        "homeassistant.config.async_hass_config_yaml", side_effect=HomeAssistantError
    ), patch("homeassistant.components.http.start_http_server_and_save_config"):
        hass = await bootstrap.async_setup_hass(
            config_dir=get_test_config_dir(),
            verbose=False,
            log_rotate_days=10,
            log_file="",
            log_no_color=False,
            skip_pip=True,
            safe_mode=False,
        )

    assert "safe_mode" in hass.config.components
    assert len(mock_mount_local_lib_path.mock_calls) == 0


async def test_setup_hass_config_dir_nonexistent(
    mock_enable_logging,
    mock_is_virtual_env,
    mock_mount_local_lib_path,
    mock_ensure_config_exists,
    mock_process_ha_config_upgrade,
):
    """Test it works."""
    mock_ensure_config_exists.return_value = False

    assert (
        await bootstrap.async_setup_hass(
            config_dir=get_test_config_dir(),
            verbose=False,
            log_rotate_days=10,
            log_file="",
            log_no_color=False,
            skip_pip=True,
            safe_mode=False,
        )
        is None
    )


async def test_setup_hass_safe_mode(
    hass,
    mock_enable_logging,
    mock_is_virtual_env,
    mock_mount_local_lib_path,
    mock_ensure_config_exists,
    mock_process_ha_config_upgrade,
):
    """Test it works."""
    # Add a config entry to storage.
    MockConfigEntry(domain="browser").add_to_hass(hass)
    hass.config_entries._async_schedule_save()
    await flush_store(hass.config_entries._store)

    with patch("homeassistant.components.browser.setup") as browser_setup, patch(
        "homeassistant.components.http.start_http_server_and_save_config"
    ):
        hass = await bootstrap.async_setup_hass(
            config_dir=get_test_config_dir(),
            verbose=False,
            log_rotate_days=10,
            log_file="",
            log_no_color=False,
            skip_pip=True,
            safe_mode=True,
        )

    assert "safe_mode" in hass.config.components
    assert len(mock_mount_local_lib_path.mock_calls) == 0

    # Validate we didn't try to set up config entry.
    assert "browser" not in hass.config.components
    assert len(browser_setup.mock_calls) == 0


async def test_setup_hass_invalid_core_config(
    mock_enable_logging,
    mock_is_virtual_env,
    mock_mount_local_lib_path,
    mock_ensure_config_exists,
    mock_process_ha_config_upgrade,
):
    """Test it works."""
    with patch(
        "homeassistant.config.async_hass_config_yaml",
        return_value={"homeassistant": {"non-existing": 1}},
    ), patch("homeassistant.components.http.start_http_server_and_save_config"):
        hass = await bootstrap.async_setup_hass(
            config_dir=get_test_config_dir(),
            verbose=False,
            log_rotate_days=10,
            log_file="",
            log_no_color=False,
            skip_pip=True,
            safe_mode=False,
        )

    assert "safe_mode" in hass.config.components


async def test_setup_safe_mode_if_no_frontend(
    mock_enable_logging,
    mock_is_virtual_env,
    mock_mount_local_lib_path,
    mock_ensure_config_exists,
    mock_process_ha_config_upgrade,
):
    """Test we setup safe mode if frontend didn't load."""
    verbose = Mock()
    log_rotate_days = Mock()
    log_file = Mock()
    log_no_color = Mock()

    with patch(
        "homeassistant.config.async_hass_config_yaml",
        return_value={
            "homeassistant": {
                "internal_url": "http://192.168.1.100:8123",
                "external_url": "https://abcdef.ui.nabu.casa",
            },
            "map": {},
            "person": {"invalid": True},
        },
    ), patch("homeassistant.components.http.start_http_server_and_save_config"):
        hass = await bootstrap.async_setup_hass(
            config_dir=get_test_config_dir(),
            verbose=verbose,
            log_rotate_days=log_rotate_days,
            log_file=log_file,
            log_no_color=log_no_color,
            skip_pip=True,
            safe_mode=False,
        )

    assert "safe_mode" in hass.config.components
    assert hass.config.config_dir == get_test_config_dir()
    assert hass.config.skip_pip
    assert hass.config.internal_url == "http://192.168.1.100:8123"
    assert hass.config.external_url == "https://abcdef.ui.nabu.casa"
