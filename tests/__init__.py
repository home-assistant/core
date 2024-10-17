"""Tests for Home Assistant."""

from syrupy.session import SnapshotSession

from .syrupy import override_syrupy_finish

# Override default finish to detect unused snapshots despite xdist
SnapshotSession.finish = override_syrupy_finish
