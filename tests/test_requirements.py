"""Test requirements module."""
import logging
import os
from unittest.mock import call, patch

import pytest

from homeassistant import loader, setup
from homeassistant.core import HomeAssistant
from homeassistant.requirements import (
    CONSTRAINT_FILE,
    RequirementsNotFound,
    async_clear_install_history,
    async_get_integration_with_requirements,
    async_process_requirements,
)

from .common import MockModule, mock_integration


def env_without_wheel_links():
    """Return env without wheel links."""
    env = dict(os.environ)
    env.pop("WHEEL_LINKS", None)
    return env


async def test_requirement_installed_in_venv(hass: HomeAssistant) -> None:
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
            timeout=60,
            no_cache_dir=False,
        )


async def test_requirement_installed_in_deps(hass: HomeAssistant) -> None:
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
            timeout=60,
            no_cache_dir=False,
        )


async def test_install_existing_package(hass: HomeAssistant) -> None:
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


async def test_install_missing_package(hass: HomeAssistant) -> None:
    """Test an install attempt on an existing package."""
    with patch(
        "homeassistant.util.package.install_package", return_value=False
    ) as mock_inst, pytest.raises(RequirementsNotFound):
        await async_process_requirements(hass, "test_component", ["hello==1.0.0"])

    assert len(mock_inst.mock_calls) == 3


async def test_install_skipped_package(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test an install attempt on a dependency that should be skipped."""
    with patch(
        "homeassistant.util.package.install_package", return_value=True
    ) as mock_inst:
        hass.config.skip_pip_packages = ["hello"]
        with caplog.at_level(logging.WARNING):
            await async_process_requirements(
                hass, "test_component", ["hello==1.0.0", "not_skipped==1.2.3"]
            )

    assert "Skipping requirement hello==1.0.0" in caplog.text

    assert len(mock_inst.mock_calls) == 1
    assert mock_inst.mock_calls[0].args[0] == "not_skipped==1.2.3"


async def test_get_integration_with_requirements(hass: HomeAssistant) -> None:
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


async def test_get_integration_with_requirements_pip_install_fails_two_passes(
    hass: HomeAssistant,
) -> None:
    """Check getting an integration with loaded requirements and the pip install fails two passes."""
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

    def _mock_install_package(package, **kwargs):
        if package == "test-comp==1.0.0":
            return True
        return False

    # 1st pass
    with pytest.raises(RequirementsNotFound), patch(
        "homeassistant.util.package.is_installed", return_value=False
    ) as mock_is_installed, patch(
        "homeassistant.util.package.install_package", side_effect=_mock_install_package
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

    assert len(mock_inst.mock_calls) == 7
    assert sorted(mock_call[1][0] for mock_call in mock_inst.mock_calls) == [
        "test-comp-after-dep==1.0.0",
        "test-comp-after-dep==1.0.0",
        "test-comp-after-dep==1.0.0",
        "test-comp-dep==1.0.0",
        "test-comp-dep==1.0.0",
        "test-comp-dep==1.0.0",
        "test-comp==1.0.0",
    ]

    # 2nd pass
    with pytest.raises(RequirementsNotFound), patch(
        "homeassistant.util.package.is_installed", return_value=False
    ) as mock_is_installed, patch(
        "homeassistant.util.package.install_package", side_effect=_mock_install_package
    ) as mock_inst:
        integration = await async_get_integration_with_requirements(
            hass, "test_component"
        )
        assert integration
        assert integration.domain == "test_component"

    assert len(mock_is_installed.mock_calls) == 0
    # On another attempt we remember failures and don't try again
    assert len(mock_inst.mock_calls) == 0

    # Now clear the history and so we try again
    async_clear_install_history(hass)

    with pytest.raises(RequirementsNotFound), patch(
        "homeassistant.util.package.is_installed", return_value=False
    ) as mock_is_installed, patch(
        "homeassistant.util.package.install_package", side_effect=_mock_install_package
    ) as mock_inst:
        integration = await async_get_integration_with_requirements(
            hass, "test_component"
        )
        assert integration
        assert integration.domain == "test_component"

    assert len(mock_is_installed.mock_calls) == 2
    assert sorted(mock_call[1][0] for mock_call in mock_is_installed.mock_calls) == [
        "test-comp-after-dep==1.0.0",
        "test-comp-dep==1.0.0",
    ]

    assert len(mock_inst.mock_calls) == 6
    assert sorted(mock_call[1][0] for mock_call in mock_inst.mock_calls) == [
        "test-comp-after-dep==1.0.0",
        "test-comp-after-dep==1.0.0",
        "test-comp-after-dep==1.0.0",
        "test-comp-dep==1.0.0",
        "test-comp-dep==1.0.0",
        "test-comp-dep==1.0.0",
    ]

    # Now clear the history and mock success
    async_clear_install_history(hass)

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

    assert len(mock_is_installed.mock_calls) == 2
    assert sorted(mock_call[1][0] for mock_call in mock_is_installed.mock_calls) == [
        "test-comp-after-dep==1.0.0",
        "test-comp-dep==1.0.0",
    ]

    assert len(mock_inst.mock_calls) == 2
    assert sorted(mock_call[1][0] for mock_call in mock_inst.mock_calls) == [
        "test-comp-after-dep==1.0.0",
        "test-comp-dep==1.0.0",
    ]


async def test_get_integration_with_missing_dependencies(hass: HomeAssistant) -> None:
    """Check getting an integration with missing dependencies."""
    hass.config.skip_pip = False
    mock_integration(
        hass,
        MockModule("test_component_after_dep"),
    )
    mock_integration(
        hass,
        MockModule(
            "test_component",
            dependencies=["test_component_dep"],
            partial_manifest={"after_dependencies": ["test_component_after_dep"]},
        ),
    )
    mock_integration(
        hass,
        MockModule(
            "test_custom_component",
            dependencies=["test_component_dep"],
            partial_manifest={"after_dependencies": ["test_component_after_dep"]},
        ),
        built_in=False,
    )
    with pytest.raises(loader.IntegrationNotFound):
        await async_get_integration_with_requirements(hass, "test_component")
    with pytest.raises(loader.IntegrationNotFound):
        await async_get_integration_with_requirements(hass, "test_custom_component")


async def test_get_built_in_integration_with_missing_after_dependencies(
    hass: HomeAssistant,
) -> None:
    """Check getting a built_in integration with missing after_dependencies results in exception."""
    hass.config.skip_pip = False
    mock_integration(
        hass,
        MockModule(
            "test_component",
            partial_manifest={"after_dependencies": ["test_component_after_dep"]},
        ),
        built_in=True,
    )
    with pytest.raises(loader.IntegrationNotFound):
        await async_get_integration_with_requirements(hass, "test_component")


async def test_get_custom_integration_with_missing_after_dependencies(
    hass: HomeAssistant,
) -> None:
    """Check getting a custom integration with missing after_dependencies."""
    hass.config.skip_pip = False
    mock_integration(
        hass,
        MockModule(
            "test_custom_component",
            partial_manifest={"after_dependencies": ["test_component_after_dep"]},
        ),
        built_in=False,
    )
    integration = await async_get_integration_with_requirements(
        hass, "test_custom_component"
    )
    assert integration
    assert integration.domain == "test_custom_component"


async def test_install_with_wheels_index(hass: HomeAssistant) -> None:
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
            timeout=60,
            no_cache_dir=True,
        )


async def test_install_on_docker(hass: HomeAssistant) -> None:
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
            timeout=60,
            no_cache_dir=True,
        )


async def test_discovery_requirements_mqtt(hass: HomeAssistant) -> None:
    """Test that we load discovery requirements."""
    hass.config.skip_pip = False
    mqtt = await loader.async_get_integration(hass, "mqtt")

    mock_integration(
        hass, MockModule("mqtt_comp", partial_manifest={"mqtt": ["foo/discovery"]})
    )
    with patch(
        "homeassistant.requirements.RequirementsManager.async_process_requirements",
    ) as mock_process:
        await async_get_integration_with_requirements(hass, "mqtt_comp")

    assert len(mock_process.mock_calls) == 3  # mqtt also depends on http
    assert mock_process.mock_calls[0][1][1] == mqtt.requirements


async def test_discovery_requirements_ssdp(hass: HomeAssistant) -> None:
    """Test that we load discovery requirements."""
    hass.config.skip_pip = False
    ssdp = await loader.async_get_integration(hass, "ssdp")

    mock_integration(
        hass, MockModule("ssdp_comp", partial_manifest={"ssdp": [{"st": "roku:ecp"}]})
    )
    with patch(
        "homeassistant.requirements.RequirementsManager.async_process_requirements",
    ) as mock_process:
        await async_get_integration_with_requirements(hass, "ssdp_comp")

    assert len(mock_process.mock_calls) == 5
    assert mock_process.mock_calls[0][1][1] == ssdp.requirements
    # Ensure zeroconf is a dep for ssdp
    assert {
        mock_process.mock_calls[1][1][0],
        mock_process.mock_calls[2][1][0],
        mock_process.mock_calls[3][1][0],
        mock_process.mock_calls[4][1][0],
    } == {"http", "network", "recorder", "zeroconf"}


@pytest.mark.parametrize(
    "partial_manifest",
    [{"zeroconf": ["_googlecast._tcp.local."]}, {"homekit": {"models": ["LIFX"]}}],
)
async def test_discovery_requirements_zeroconf(
    hass: HomeAssistant, partial_manifest
) -> None:
    """Test that we load discovery requirements."""
    hass.config.skip_pip = False
    zeroconf = await loader.async_get_integration(hass, "zeroconf")

    mock_integration(
        hass,
        MockModule("comp", partial_manifest=partial_manifest),
    )

    with patch(
        "homeassistant.requirements.RequirementsManager.async_process_requirements",
    ) as mock_process:
        await async_get_integration_with_requirements(hass, "comp")

    assert len(mock_process.mock_calls) == 4  # zeroconf also depends on http
    assert mock_process.mock_calls[0][1][1] == zeroconf.requirements


async def test_discovery_requirements_dhcp(hass: HomeAssistant) -> None:
    """Test that we load dhcp discovery requirements."""
    hass.config.skip_pip = False
    dhcp = await loader.async_get_integration(hass, "dhcp")

    mock_integration(
        hass,
        MockModule(
            "comp",
            partial_manifest={
                "dhcp": [{"hostname": "somfy_*", "macaddress": "B8B7F1*"}]
            },
        ),
    )
    with patch(
        "homeassistant.requirements.RequirementsManager.async_process_requirements",
    ) as mock_process:
        await async_get_integration_with_requirements(hass, "comp")

    assert len(mock_process.mock_calls) == 1  # dhcp does not depend on http
    assert mock_process.mock_calls[0][1][1] == dhcp.requirements
