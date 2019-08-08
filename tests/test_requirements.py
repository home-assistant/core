"""Test requirements module."""
import os
from pathlib import Path
from unittest.mock import patch, call

from homeassistant import setup
from homeassistant.requirements import (
    CONSTRAINT_FILE,
    async_process_requirements,
    PROGRESS_FILE,
    _install,
)

from tests.common import (
    get_test_home_assistant,
    MockModule,
    mock_coro,
    mock_integration,
)


class TestRequirements:
    """Test the requirements module."""

    hass = None
    backup_cache = None

    # pylint: disable=invalid-name, no-self-use
    def setup_method(self, method):
        """Set up the test."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Clean up."""
        self.hass.stop()

    @patch("os.path.dirname")
    @patch("homeassistant.util.package.is_virtual_env", return_value=True)
    @patch("homeassistant.util.package.is_docker_env", return_value=False)
    @patch("homeassistant.util.package.install_package", return_value=True)
    def test_requirement_installed_in_venv(
        self, mock_install, mock_denv, mock_venv, mock_dirname
    ):
        """Test requirement installed in virtual environment."""
        mock_dirname.return_value = "ha_package_path"
        self.hass.config.skip_pip = False
        mock_integration(self.hass, MockModule("comp", requirements=["package==0.0.1"]))
        assert setup.setup_component(self.hass, "comp", {})
        assert "comp" in self.hass.config.components
        assert mock_install.call_args == call(
            "package==0.0.1",
            constraints=os.path.join("ha_package_path", CONSTRAINT_FILE),
            no_cache_dir=False,
        )

    @patch("os.path.dirname")
    @patch("homeassistant.util.package.is_virtual_env", return_value=False)
    @patch("homeassistant.util.package.is_docker_env", return_value=False)
    @patch("homeassistant.util.package.install_package", return_value=True)
    def test_requirement_installed_in_deps(
        self, mock_install, mock_denv, mock_venv, mock_dirname
    ):
        """Test requirement installed in deps directory."""
        mock_dirname.return_value = "ha_package_path"
        self.hass.config.skip_pip = False
        mock_integration(self.hass, MockModule("comp", requirements=["package==0.0.1"]))
        assert setup.setup_component(self.hass, "comp", {})
        assert "comp" in self.hass.config.components
        assert mock_install.call_args == call(
            "package==0.0.1",
            target=self.hass.config.path("deps"),
            constraints=os.path.join("ha_package_path", CONSTRAINT_FILE),
            no_cache_dir=False,
        )


async def test_install_existing_package(hass):
    """Test an install attempt on an existing package."""
    with patch(
        "homeassistant.util.package.install_package", return_value=mock_coro(True)
    ) as mock_inst:
        assert await async_process_requirements(
            hass, "test_component", ["hello==1.0.0"]
        )

    assert len(mock_inst.mock_calls) == 1

    with patch("homeassistant.util.package.is_installed", return_value=True), patch(
        "homeassistant.util.package.install_package"
    ) as mock_inst:
        assert await async_process_requirements(
            hass, "test_component", ["hello==1.0.0"]
        )

    assert len(mock_inst.mock_calls) == 0


async def test_install_with_wheels_index(hass):
    """Test an install attempt with wheels index URL."""
    hass.config.skip_pip = False
    mock_integration(hass, MockModule("comp", requirements=["hello==1.0.0"]))

    with patch("homeassistant.util.package.is_installed", return_value=False), patch(
        "homeassistant.util.package.is_docker_env", return_value=True
    ), patch("homeassistant.util.package.install_package") as mock_inst, patch.dict(
        os.environ, {"WHEELS_LINKS": "https://wheels.hass.io/test"}
    ), patch(
        "os.path.dirname"
    ) as mock_dir:
        mock_dir.return_value = "ha_package_path"
        assert await setup.async_setup_component(hass, "comp", {})
        assert "comp" in hass.config.components
        print(mock_inst.call_args)
        assert mock_inst.call_args == call(
            "hello==1.0.0",
            find_links="https://wheels.hass.io/test",
            constraints=os.path.join("ha_package_path", CONSTRAINT_FILE),
            no_cache_dir=True,
        )


async def test_install_on_docker(hass):
    """Test an install attempt on an docker system env."""
    hass.config.skip_pip = False
    mock_integration(hass, MockModule("comp", requirements=["hello==1.0.0"]))

    with patch("homeassistant.util.package.is_installed", return_value=False), patch(
        "homeassistant.util.package.is_docker_env", return_value=True
    ), patch("homeassistant.util.package.install_package") as mock_inst, patch(
        "os.path.dirname"
    ) as mock_dir:
        mock_dir.return_value = "ha_package_path"
        assert await setup.async_setup_component(hass, "comp", {})
        assert "comp" in hass.config.components
        print(mock_inst.call_args)
        assert mock_inst.call_args == call(
            "hello==1.0.0",
            constraints=os.path.join("ha_package_path", CONSTRAINT_FILE),
            no_cache_dir=True,
        )


async def test_progress_lock(hass):
    """Test an install attempt on an existing package."""
    progress_path = Path(hass.config.path(PROGRESS_FILE))
    kwargs = {"hello": "world"}

    def assert_env(req, **passed_kwargs):
        """Assert the env."""
        assert progress_path.exists()
        assert req == "hello"
        assert passed_kwargs == kwargs
        return True

    with patch("homeassistant.util.package.install_package", side_effect=assert_env):
        _install(hass, "hello", kwargs)

    assert not progress_path.exists()
