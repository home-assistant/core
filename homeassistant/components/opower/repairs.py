"""Repair and migration utilities for Opower data."""

from datetime import datetime
from typing import Final

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.issue_registry import IssueSeverity
from homeassistant.util import dt as dt_util

from .const import DOMAIN

# These patterns identify statistics that might need repair:
# - Cost statistics: When negative costs should be in compensation statistics
# - Consumption statistics: When negative consumption should be in return statistics
STATISTIC_PATTERNS: Final[dict[str, dict[str, str]]] = {
    "negative_cost_statistics": {
        "source": "_energy_cost",  # Original statistic containing negatives
        "target": "_energy_compensation",  # Where negatives should be moved to
    },
    "negative_consumption_statistics": {
        "source": "_energy_consumption",
        "target": "_energy_return",
    },
}


async def find_statistics_with_negative_values(
    hass: HomeAssistant,
) -> dict[str, list[str]]:
    """Find statistics that have negative values that should be moved to separate statistics.

    For example:
    - Negative costs should be moved to compensation statistics
    - Negative consumption should be moved to return statistics

    Returns a dict mapping issue type to list of affected statistic IDs.
    """
    # Track which statistics need repair for each issue type
    needs_repair: dict[str, list[str]] = {
        issue_type: [] for issue_type in STATISTIC_PATTERNS
    }

    # Look through entire history starting from Unix epoch
    start_time = datetime.fromtimestamp(0, tz=dt_util.UTC)

    # Check monthly/daily/hourly statistics since negative values might only appear in certain resolutions
    for period in ("month", "day", "hour"):
        # Use recorder's executor to access the database
        all_stats = await get_instance(hass).async_add_executor_job(
            statistics_during_period,
            hass,
            start_time,
            None,  # end_time
            None,  # statistic_ids
            period,
            None,  # units
            {"sum"},  # types
        )

        for statistic_id, measurements in all_stats.items():
            # Only look at Opower statistics
            if not statistic_id.startswith(f"{DOMAIN}:"):
                continue

            # Skip if we already found this statistic needs repair
            if any(
                statistic_id in found_stats for found_stats in needs_repair.values()
            ):
                continue

            # Check if any measurements have negative values
            has_negative_values = any(
                (sum_value := measurement.get("sum")) is not None
                and float(sum_value) < 0
                for measurement in measurements
            )
            if not has_negative_values:
                continue

            # Determine which type of repair is needed
            for issue_type, patterns in STATISTIC_PATTERNS.items():
                source_pattern = patterns["source"]
                target_pattern = patterns["target"]
                if (
                    source_pattern in statistic_id
                    and target_pattern not in statistic_id
                ):
                    needs_repair[issue_type].append(statistic_id)
                    break

    return needs_repair


async def create_negative_statistics_issues(hass: HomeAssistant) -> None:
    """Create repair issues for statistics with negative values that need to be split.

    For each type of repair needed, creates a repair issue listing the affected statistics.
    The issue tells users which statistics contain negative values that should be moved
    to separate positive/negative statistics.
    """
    needs_repair = await find_statistics_with_negative_values(hass)
    if not any(needs_repair.values()):
        return

    issue_registry = ir.async_get(hass)

    # Create an issue for each type of repair needed
    for issue_type, affected_statistics in needs_repair.items():
        if not affected_statistics:
            continue

        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_type,
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key=issue_type,
            translation_placeholders={
                "statistic_ids": ", ".join(sorted(affected_statistics))
            },
        )

    # Clean up any old format issues
    for issue in list(issue_registry.issues.values()):
        if issue.domain != DOMAIN and issue.issue_id in STATISTIC_PATTERNS:
            issue_registry.async_delete(issue.domain, issue.issue_id)


async def async_validate_negative_stats(hass: HomeAssistant) -> None:
    """Check for Opower statistics that need repair."""
    affected_stats = await find_statistics_with_negative_values(hass)
    if any(affected_stats.values()):
        await create_negative_statistics_issues(hass)
