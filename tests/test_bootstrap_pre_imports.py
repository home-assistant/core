"""Test bootstrap pre imports.

This test must be minimal as it tests that discovery
and stage1 integrations are not pre-imported as a side
effect of importing the pre-imports.
"""


import sys

from homeassistant import bootstrap, loader
from homeassistant.core import HomeAssistant


async def test_bootstrap_does_not_preload_discovery_integrations(
    hass: HomeAssistant,
) -> None:
    """Test that the bootstrap does not preload discovery integrations.

    If this test fails it means that discovery integrations are being
    loaded too soon and will not get their requirements updated
    before they are loaded at runtime.
    """
    # Ensure no discovery integrations have been imported
    # as a side effect of importing the pre-imports
    for integration in bootstrap.DISCOVERY_INTEGRATIONS:
        assert f"homeassistant.components.{integration}" not in sys.modules


async def test_bootstrap_does_not_preload_stage_1_integrations(
    hass: HomeAssistant,
) -> None:
    """Test that the bootstrap does not preload stage 1 integrations.

    If this test fails it means that stage1 integrations are being
    loaded too soon and will not get their requirements updated
    before they are loaded at runtime.
    """
    # Ensure no stage1 integrations have been imported
    # as a side effect of importing the pre-imports
    for integration in bootstrap.STAGE_1_INTEGRATIONS:
        assert f"homeassistant.components.{integration}" not in sys.modules


async def test_frontend_deps_pre_import_no_requirements(hass: HomeAssistant) -> None:
    """Test frontend dependencies are pre-imported and do not have any requirements."""
    pre_imports = [
        name.removesuffix("_pre_import")
        for name in dir(bootstrap)
        if name.endswith("_pre_import")
    ]

    # Make sure future refactoring does not
    # accidentally remove the pre-imports
    # or change the naming convention without
    # updating this test.
    assert len(pre_imports) > 3

    for pre_import in pre_imports:
        integration = await loader.async_get_integration(hass, pre_import)
        assert not integration.requirements
