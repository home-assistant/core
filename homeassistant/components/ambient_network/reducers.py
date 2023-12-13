"""Data reduction functions for the Ambient Weather Network integration."""
from __future__ import annotations

from typing import Any

import numpy as np


class Reducers:
    """Data reduction functions."""

    @staticmethod
    def remove_outliers(values: list[Any]) -> list[Any]:
        """Remove outliers from a list of data values."""

        if len(values) < 3:
            return values

        # Calculate the median.
        median = np.median(values)

        # Calculate the absolute deviations from the median.
        abs_deviations = np.abs(values - median)

        # Calculate the median absolute deviation (MAD).
        mad = np.median(abs_deviations)

        # Calculate the upper and lower bounds.
        upper_bound = median + 2.5 * mad
        lower_bound = median - 2.5 * mad

        # Eliminate any data points that fall outside the bounds.
        return list(filter(lambda value: lower_bound <= value <= upper_bound, values))

    @staticmethod
    def mean(values: list[Any]) -> Any:
        """Merge data from multiple stations by taking the mean value."""

        result = np.median(Reducers.remove_outliers(values))
        return result

    @staticmethod
    def max(values: list[Any]) -> Any:
        """Merge data from multiple stations by taking the max value."""

        result = np.max(values)
        return result
