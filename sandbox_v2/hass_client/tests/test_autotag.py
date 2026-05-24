"""Tests for the compat-lane ``MockConfigEntry.add_to_hass`` autotag patch.

These pin the sync classifier behaviour directly (no HA Core fixtures
needed). The end-to-end "patched ``add_to_hass`` mutates ``entry.data``"
case lives on the HA-core side at
``tests/components/sandbox_v2/test_testing_plugins.py`` where
``MockConfigEntry`` is importable through the running pytest session.
"""

from hass_client.testing._autotag import classify_domain_sync


def test_classify_known_builtin_returns_built_in_group() -> None:
    """A vanilla built-in integration routes to ``built-in``."""
    # ``light`` is a standard built-in with no incompatible platform.
    assert classify_domain_sync("light") == "built-in"


def test_classify_always_main_returns_none() -> None:
    """An ``ALWAYS_MAIN`` domain returns ``None`` (== stay on main)."""
    assert classify_domain_sync("automation") is None
    assert classify_domain_sync("script") is None


def test_classify_incompatible_platform_returns_none() -> None:
    """An integration shipping a deny-listed platform routes to main.

    ``cloud`` is in ``ALWAYS_MAIN`` so it short-circuits; pick ``demo``
    instead — it ships an ``stt`` platform.
    """
    # Use the deny-list path: any integration that ships ``stt.py`` /
    # ``tts.py`` / etc. classifies to main. ``demo`` provides every
    # platform; assert the path fires for it.
    assert classify_domain_sync("demo") is None


def test_classify_unknown_domain_returns_custom_group() -> None:
    """A domain we can't find on disk is treated as a custom integration."""
    assert classify_domain_sync("not_a_real_integration_xyz") == "custom"


def test_classify_system_integration_returns_none() -> None:
    """A system-type integration stays on main.

    ``websocket_api`` is marked ``integration_type: system`` in its
    manifest and is the canonical example used by the classifier.
    """
    assert classify_domain_sync("websocket_api") is None
