"""Common methods used across tests for Clicky."""

from datetime import date as date_
from typing import Any

from pyclicky import Report, ReportDate, ReportItem


def _make_report(value: Any, report_type: str = "dummy") -> Report:
    """Build a minimal single-value Report for tests."""
    return Report(
        type=report_type,
        dates=[
            ReportDate(
                start=date_(2026, 8, 4),
                end=date_(2026, 8, 4),
                items=[ReportItem(title=None, value=value)],
            )
        ],
    )


def _make_empty_report(report_type: str = "dummy") -> Report:
    """Build a Report without any dates, whose value is None."""
    return Report(type=report_type, dates=[])
