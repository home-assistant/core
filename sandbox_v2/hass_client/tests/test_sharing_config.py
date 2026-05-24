"""Phase 7 tests for the SharingConfig + CLI parsing on the runtime side."""

from hass_client.sandbox import SandboxRuntime, SharingConfig
from hass_client.sandbox_v2.__main__ import _build_parser
import pytest


def test_sharing_config_defaults_locked_down() -> None:
    """All sharing flags default to False — the locked-down posture."""
    cfg = SharingConfig()
    assert cfg.share_states is False
    assert cfg.share_entity_registry is False
    assert cfg.share_areas is False


def test_runtime_defaults_to_locked_down_sharing() -> None:
    """SandboxRuntime() without an explicit sharing= argument is locked down."""
    rt = SandboxRuntime(url="ws://x", token="t", group="g")
    assert rt.sharing == SharingConfig()


def test_runtime_stores_explicit_sharing() -> None:
    """An explicit SharingConfig is preserved on the runtime."""
    sharing = SharingConfig(share_states=True, share_areas=True)
    rt = SandboxRuntime(url="ws://x", token="t", group="g", sharing=sharing)
    assert rt.sharing is sharing


@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        ([], SharingConfig()),
        (
            ["--share-states"],
            SharingConfig(share_states=True),
        ),
        (
            ["--share-states", "--share-entity-registry"],
            SharingConfig(share_states=True, share_entity_registry=True),
        ),
        (
            ["--share-states", "--share-entity-registry", "--share-areas"],
            SharingConfig(
                share_states=True, share_entity_registry=True, share_areas=True
            ),
        ),
    ],
    ids=["none", "states", "states+registry", "all"],
)
def test_cli_share_flags(flags: list[str], expected: SharingConfig) -> None:
    """The CLI parser turns --share-* flags into the matching SharingConfig."""
    base = ["--group", "g", "--url", "ws://x", "--token", "t"]
    args = _build_parser().parse_args(base + flags)
    assert (
        SharingConfig(
            share_states=args.share_states,
            share_entity_registry=args.share_entity_registry,
            share_areas=args.share_areas,
        )
        == expected
    )
