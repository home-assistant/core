"""Tests for the syrupy extension."""

from syrupy.session import ItemStatus

from tests.syrupy import _FakePytestItem, _merge_serialized_report


class _MockReport:
    """Minimal mock for SnapshotReport."""

    def __init__(self) -> None:
        self.discovered = object()
        self.created = object()
        self.failed = object()
        self.matched = object()
        self.updated = object()
        self.used = object()
        self.collected_items: set = set()
        self.selected_items: dict[str, ItemStatus] = {}


def test_merge_serialized_report_deduplicates_collected_items() -> None:
    """Test that _merge_serialized_report deduplicates collected items by nodeid and name."""
    report = _MockReport()

    existing = _FakePytestItem(
        {
            "nodeid": "tests/test_foo.py::test_bar",
            "name": "test_bar",
            "path": "tests/test_foo.py",
            "modulename": "tests.test_foo",
            "methodname": "test_bar",
        }
    )
    report.collected_items.add(existing)

    _merge_serialized_report(
        report,  # type: ignore[arg-type]
        {
            "discovered": {},
            "created": {},
            "failed": {},
            "matched": {},
            "updated": {},
            "used": {},
            "_collected_items": [
                {
                    "nodeid": "tests/test_foo.py::test_bar",
                    "name": "test_bar",
                    "path": "tests/test_foo.py",
                    "modulename": "tests.test_foo",
                    "methodname": "test_bar",
                }
            ],
            "_selected_items": {},
        },
    )

    assert len(report.collected_items) == 1
