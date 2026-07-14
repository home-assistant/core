"""Demonstration tests for the runtime supported-features check.

Shows the runtime check catching a *dynamically* declared feature that the
static pylint checker deliberately skips (see the ``dynamic_call_declaration``
case in ``tests/pylint/test_supported_features.py`` for the static side), and
shows the entity-add hook firing through the real ``EntityPlatform`` flow.
"""

from homeassistant.components.cover import CoverEntity, CoverEntityFeature
from homeassistant.core import HomeAssistant

from .common import MockEntityPlatform
from .supported_features_runtime import check_entity, collect_via_add_hook


def _features_from_caps() -> CoverEntityFeature:
    """Stand-in for a value computed from device capabilities at runtime."""
    return CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE


class DynamicCover(CoverEntity):
    """Declares OPEN|CLOSE from a computed value, implements only open."""

    _attr_is_closed = False
    _attr_is_opening = False
    _attr_is_closing = False

    def __init__(self) -> None:
        """Set supported_features the way many real integrations do."""
        self._attr_supported_features = _features_from_caps()

    async def async_open_cover(self, **kwargs: object) -> None:
        """Open the cover."""


class ImplementedCover(CoverEntity):
    """Declares OPEN|CLOSE from a computed value and implements both."""

    def __init__(self) -> None:
        """Set supported_features the way many real integrations do."""
        self._attr_supported_features = _features_from_caps()

    async def async_open_cover(self, **kwargs: object) -> None:
        """Open the cover."""

    async def async_close_cover(self, **kwargs: object) -> None:
        """Close the cover."""


def test_runtime_detects_dynamically_declared_feature() -> None:
    """The instance advertises CLOSE via a computed value but lacks the method."""
    violations = check_entity(DynamicCover(), "cover")
    assert [flag for flag, _ in violations] == ["CLOSE"]


def test_runtime_clean_when_implemented() -> None:
    """No violation when both methods are implemented."""
    assert check_entity(ImplementedCover(), "cover") == []


async def test_add_hook_collects_violation(hass: HomeAssistant) -> None:
    """The hook fires through the real EntityPlatform add flow."""
    platform = MockEntityPlatform(hass, domain="cover")
    with collect_via_add_hook(module_prefixes=("tests.",)) as collected:
        await platform.async_add_entities([DynamicCover()])
    assert [(v["feature"], v["domain"]) for v in collected] == [("CLOSE", "cover")]
