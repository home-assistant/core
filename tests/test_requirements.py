"""Test requirements module."""
import os

import pytest

from homeassistant import loader, setup
from homeassistant.requirements import (
    CONSTRAINT_FILE,
    RequirementsNotFound,
    async_get_integration_with_requirements,
    async_process_requirements,
)

from tests.async_mock import call, patch
from tests.common import MockModule, mock_integration


def env_without_wheel_links():
    """Return env without wheel links."""
    env = dict(os.environ)
    env.pop("WHEEL_LINKS", None)
    return env


async def test_requirement_installed_in_venv(hass):
    """Test requirement installed in virtual environment."""
    with patch("os.path.dirname", return_value="ha_package_path"), patch(
        "homeassistant.util.package.is_virtual_env", return_value=True
    ), patch("homeassistant.util.package.is_docker_env", return_value=False), patch(
        "homeassistant.util.package.install_package", return_value=True
    ) as mock_install, patch.dict(
        os.environ, env_without_wheel_links(), clear=True
    ):
        hass.config.skip_pip = False
        mock_integration(hass, MockModule("comp", requirements=["package==0.0.1"]))
        assert await setup.async_setup_component(hass, "comp", {})
        assert "comp" in hass.config.components
        assert mock_install.call_args == call(
            "package==0.0.1",
            constraints=os.path.join("ha_package_path", CONSTRAINT_FILE),
            no_cache_dir=False,
        )


async def test_requirement_installed_in_deps(hass):
    """Test requirement installed in deps directory."""
    with patch("os.path.dirname", return_value="ha_package_path"), patch(
        "homeassistant.util.package.is_virtual_env", return_value=False
    ), patch("homeassistant.util.package.is_docker_env", return_value=False), patch(
        "homeassistant.util.package.install_package", return_value=True
    ) as mock_install, patch.dict(
        os.environ, env_without_wheel_links(), clear=True
    ):
        hass.config.skip_pip = False
        mock_integration(hass, MockModule("comp", requirements=["package==0.0.1"]))
        assert await setup.async_setup_component(hass, "comp", {})
        assert "comp" in hass.config.components
        assert mock_install.call_args == call(
            "package==0.0.1",
            target=hass.config.path("deps"),
            constraints=os.path.join("ha_package_path", CONSTRAINT_FILE),
            no_cache_dir=False,
        )


async def test_install_existing_package(hass):
    """Test an install attempt on an existing package."""
    with patch(
        "homeassistant.util.package.install_package", return_value=True
    ) as mock_inst:
        await async_process_requirements(hass, "test_component", ["hello==1.0.0"])

    assert len(mock_inst.mock_calls) == 1

    with patch("homeassistant.util.package.is_installed", return_value=True), patch(
        "homeassistant.util.package.install_package"
    ) as mock_inst:
        await async_process_requirements(hass, "test_component", ["hello==1.0.0"])

    assert len(mock_inst.mock_calls) == 0


async def test_install_missing_package(hass):
    """Test an install attempt on an existing package."""
    with patch(
        "homeassistant.util.package.install_package", return_value=False
    ) as mock_inst:
        with pytest.raises(RequirementsNotFound):
            await async_process_requirements(hass, "test_component", ["hello==1.0.0"])

    assert len(mock_inst.mock_calls) == 1


async def test_get_integration_with_requirements(hass):
    """Check getting an integration with loaded requirements."""
    hass.config.skip_pip = False
    mock_integration(
        hass, MockModule("test_component_dep", requirements=["test-comp-dep==1.0.0"])
    )
    mock_integration(
        hass,
        MockModule(
            "test_component_after_dep", requirements=["test-comp-after-dep==1.0.0"]
        ),
    )
    mock_integration(
        hass,
        MockModule(
            "test_component",
            requirements=["test-comp==1.0.0"],
            dependencies=["test_component_dep"],
            partial_manifest={"after_dependencies": ["test_component_after_dep"]},
        ),
    )

    with patch(
        "homeassistant.util.package.is_installed", return_value=False
    ) as mock_is_installed, patch(
        "homeassistant.util.package.install_package", return_value=True
    ) as mock_inst:

        integration = await async_get_integration_with_requirements(
            hass, "test_component"
        )
        assert integration
        assert integration.domain == "test_component"

    assert len(mock_is_installed.mock_calls) == 3
    assert sorted(mock_call[1][0] for mock_call in mock_is_installed.mock_calls) == [
        "test-comp-after-dep==1.0.0",
        "test-comp-dep==1.0.0",
        "test-comp==1.0.0",
    ]

    assert len(mock_inst.mock_calls) == 3
    assert sorted(mock_call[1][0] for mock_call in mock_inst.mock_calls) == [
        "test-comp-after-dep==1.0.0",
        "test-comp-dep==1.0.0",
        "test-comp==1.0.0",
    ]


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
    ) as mock_dir, patch.dict(
        os.environ, env_without_wheel_links(), clear=True
    ):
        mock_dir.return_value = "ha_package_path"
        assert await setup.async_setup_component(hass, "comp", {})
        assert "comp" in hass.config.components

        assert mock_inst.call_args == call(
            "hello==1.0.0",
            constraints=os.path.join("ha_package_path", CONSTRAINT_FILE),
            no_cache_dir=True,
        )


async def test_discovery_requirements_ssdp(hass):
    """Test that we load discovery requirements."""
    hass.config.skip_pip = False
    ssdp = await loader.async_get_integration(hass, "ssdp")

    mock_integration(
        hass, MockModule("ssdp_comp", partial_manifest={"ssdp": [{"st": "roku:ecp"}]})
    )
    with patch(
        "homeassistant.requirements.async_process_requirements",
    ) as mock_process:
        await async_get_integration_with_requirements(hass, "ssdp_comp")

    assert len(mock_process.mock_calls) == 3
    assert mock_process.mock_calls[0][1][2] == ssdp.requirements
    # Ensure zeroconf is a dep for ssdp
    assert mock_process.mock_calls[1][1][1] == "zeroconf"


@pytest.mark.parametrize(
    "partial_manifest",
    [{"zeroconf": ["_googlecast._tcp.local."]}, {"homekit": {"models": ["LIFX"]}}],
)
async def test_discovery_requirements_zeroconf(hass, partial_manifest):
    """Test that we load discovery requirements."""
    hass.config.skip_pip = False
    zeroconf = await loader.async_get_integration(hass, "zeroconf")

    mock_integration(
        hass,
        MockModule("comp", partial_manifest=partial_manifest),
    )

    with patch(
        "homeassistant.requirements.async_process_requirements",
    ) as mock_process:
        await async_get_integration_with_requirements(hass, "comp")

    assert len(mock_process.mock_calls) == 2  # zeroconf also depends on http
    assert mock_process.mock_calls[0][1][2] == zeroconf.requirements
