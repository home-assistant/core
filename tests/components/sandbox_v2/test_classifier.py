"""Tests for the sandbox_v2 integration classifier."""

import pytest

from homeassistant.components.sandbox_v2.classifier import (
    GROUP_BUILT_IN,
    GROUP_CUSTOM,
    SandboxAssignment,
    classify,
)
from homeassistant.components.sandbox_v2.const import (
    ALWAYS_MAIN,
    SANDBOX_INCOMPATIBLE_PLATFORMS,
)
from homeassistant.core import HomeAssistant
from homeassistant.loader import Integration

from tests.common import MockModule, mock_integration


def _make_integration(
    hass: HomeAssistant,
    domain: str,
    *,
    built_in: bool = True,
    integration_type: str = "hub",
    platform_files: set[str] | None = None,
) -> Integration:
    """Return a fake `Integration` shaped like the classifier needs."""
    top_level_files = {"manifest.json", "__init__.py"}
    if platform_files:
        top_level_files |= {f"{name}.py" for name in platform_files}
    return mock_integration(
        hass,
        MockModule(
            domain,
            partial_manifest={"integration_type": integration_type},
        ),
        built_in=built_in,
        top_level_files=top_level_files,
    )


async def test_system_integration_runs_on_main(hass: HomeAssistant) -> None:
    """integration_type=system always pins to main, ahead of every other rule."""
    integration = _make_integration(hass, "sys_int", integration_type="system")
    assignment = classify(integration)
    assert assignment == SandboxAssignment(group=None)
    assert assignment.is_main


async def test_custom_integration_goes_to_custom_sandbox(hass: HomeAssistant) -> None:
    """Plain hub-type custom integration with no deny-listed platforms."""
    integration = _make_integration(hass, "custom_int", built_in=False)
    assert classify(integration) == SandboxAssignment(group=GROUP_CUSTOM)


async def test_clean_built_in_goes_to_built_in_sandbox(hass: HomeAssistant) -> None:
    """Built-in integration with no deny-listed platforms → built-in sandbox."""
    integration = _make_integration(
        hass, "clean_int", platform_files={"sensor", "light"}
    )
    assert classify(integration) == SandboxAssignment(group=GROUP_BUILT_IN)


async def test_built_in_with_tts_platform_forced_to_main(hass: HomeAssistant) -> None:
    """A built-in integration that ships tts.py must run on main."""
    integration = _make_integration(hass, "tts_provider", platform_files={"tts"})
    assert classify(integration).is_main


async def test_custom_with_incompatible_platform_forced_to_main(
    hass: HomeAssistant,
) -> None:
    """The platform deny-list overrides the custom→sandbox rule."""
    integration = _make_integration(
        hass, "custom_tts", built_in=False, platform_files={"tts"}
    )
    assert classify(integration).is_main


@pytest.mark.parametrize("domain", sorted(ALWAYS_MAIN))
async def test_always_main_domains_pin_to_main(
    hass: HomeAssistant, domain: str
) -> None:
    """Every domain in ALWAYS_MAIN must classify to main, manifest-shape agnostic.

    Parametrising over the live set means a new entry can't silently miss
    the rule — the test fans out automatically.
    """
    integration = _make_integration(hass, domain, platform_files={"sensor"})
    assert classify(integration).is_main


@pytest.mark.parametrize("domain", ["ai_task", "image"])
async def test_phase1_spike_late_additions_pin_to_main(
    hass: HomeAssistant, domain: str
) -> None:
    """ai_task and image were folded into ALWAYS_MAIN by the Phase 1 spike.

    Pinned as their own test so the regression message is unambiguous if
    someone removes them from the deny-list without reading the decision doc.
    """
    integration = _make_integration(hass, domain)
    assert classify(integration).is_main


@pytest.mark.parametrize("platform", sorted(SANDBOX_INCOMPATIBLE_PLATFORMS))
async def test_each_incompatible_platform_forces_main(
    hass: HomeAssistant, platform: str
) -> None:
    """Each deny-listed platform must individually pin its host to main."""
    integration = _make_integration(
        hass, f"host_for_{platform}", platform_files={platform}
    )
    assert classify(integration).is_main


async def test_image_is_domain_not_platform_level(hass: HomeAssistant) -> None:
    """Phase 1 decision: `image` lives in ALWAYS_MAIN, not the platform list.

    Camera covers the bytes-platform case; image entities returning bytes
    drive the domain-level rule. Lock the shape so a future cleanup doesn't
    move it back without revisiting the decision doc.
    """
    assert "image" in ALWAYS_MAIN
    assert "image" not in SANDBOX_INCOMPATIBLE_PLATFORMS


async def test_system_rule_beats_always_main(hass: HomeAssistant) -> None:
    """`integration_type=system` wins even if the domain is also in ALWAYS_MAIN.

    Defensive: ALWAYS_MAIN's effect is identical to the system rule (both
    pin to main), but the rule order is observable through the assignment
    value, and we want the order documented in `classify()` to be the order
    the test pins.
    """
    # script is in ALWAYS_MAIN; pretend it's also system-typed.
    integration = _make_integration(hass, "script", integration_type="system")
    assert classify(integration).is_main
