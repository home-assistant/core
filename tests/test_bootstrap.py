"""Test the bootstrapping."""
# pylint: disable=protected-access
import logging
import os
from unittest.mock import Mock, patch

from homeassistant import bootstrap
import homeassistant.config as config_util
import homeassistant.util.dt as dt_util

from tests.common import (
    MockModule,
    get_test_config_dir,
    mock_coro,
    mock_integration,
    patch_yaml_files,
)

ORIG_TIMEZONE = dt_util.DEFAULT_TIME_ZONE
VERSION_PATH = os.path.join(get_test_config_dir(), config_util.VERSION_FILE)

_LOGGER = logging.getLogger(__name__)


# prevent .HA_VERSION file from being written
@patch("homeassistant.bootstrap.conf_util.process_ha_config_upgrade", Mock())
@patch(
    "homeassistant.util.location.async_detect_location_info",
    Mock(return_value=mock_coro(None)),
)
@patch("os.path.isfile", Mock(return_value=True))
@patch("os.access", Mock(return_value=True))
@patch("homeassistant.bootstrap.async_enable_logging", Mock(return_value=True))
async def test_from_config_file(hass):
    """Test with configuration file."""
    components = set(["browser", "conversation", "script"])
    files = {"config.yaml": "".join("{}:\n".format(comp) for comp in components)}

    with patch_yaml_files(files, True):
        await bootstrap.async_from_config_file("config.yaml", hass)

    assert components == hass.config.components


@patch("homeassistant.bootstrap.async_enable_logging", Mock())
async def test_home_assistant_core_config_validation(hass):
    """Test if we pass in wrong information for HA conf."""
    # Extensive HA conf validation testing is done
    result = await bootstrap.async_from_config_dict(
        {"homeassistant": {"latitude": "some string"}}, hass
    )
    assert result is None


async def test_async_from_config_file_not_mount_deps_folder(loop):
    """Test that we not mount the deps folder inside async_from_config_file."""
    hass = Mock(async_add_executor_job=Mock(side_effect=lambda *args: mock_coro()))

    with patch("homeassistant.bootstrap.is_virtual_env", return_value=False), patch(
        "homeassistant.bootstrap.async_enable_logging", return_value=mock_coro()
    ), patch(
        "homeassistant.bootstrap.async_mount_local_lib_path", return_value=mock_coro()
    ) as mock_mount, patch(
        "homeassistant.bootstrap.async_from_config_dict", return_value=mock_coro()
    ):

        await bootstrap.async_from_config_file("mock-path", hass)
        assert len(mock_mount.mock_calls) == 1

    with patch("homeassistant.bootstrap.is_virtual_env", return_value=True), patch(
        "homeassistant.bootstrap.async_enable_logging", return_value=mock_coro()
    ), patch(
        "homeassistant.bootstrap.async_mount_local_lib_path", return_value=mock_coro()
    ) as mock_mount, patch(
        "homeassistant.bootstrap.async_from_config_dict", return_value=mock_coro()
    ):

        await bootstrap.async_from_config_file("mock-path", hass)
        assert len(mock_mount.mock_calls) == 0


async def test_load_hassio(hass):
    """Test that we load Hass.io component."""
    with patch.dict(os.environ, {}, clear=True):
        assert bootstrap._get_domains(hass, {}) == set()

    with patch.dict(os.environ, {"HASSIO": "1"}):
        assert bootstrap._get_domains(hass, {}) == {"hassio"}


async def test_empty_setup(hass):
    """Test an empty set up loads the core."""
    await bootstrap._async_set_up_integrations(hass, {})
    for domain in bootstrap.CORE_INTEGRATIONS:
        assert domain in hass.config.components, domain


async def test_core_failure_aborts(hass, caplog):
    """Test failing core setup aborts further setup."""
    with patch(
        "homeassistant.components.homeassistant.async_setup",
        return_value=mock_coro(False),
    ):
        await bootstrap._async_set_up_integrations(hass, {"group": {}})

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
