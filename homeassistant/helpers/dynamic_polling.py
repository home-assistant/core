"""Dynamic polling helper."""
from __future__ import annotations

from collections.abc import Callable
from logging import getLogger
from typing import Any

import numdifftools as nd
import numpy as np
import scipy.stats as st

LOGGER = getLogger(__name__)


def get_best_distribution(data: list[float]) -> Any:
    """Get distribution based on p value."""
    if len(data) == 1:
        return st.uniform(0, data[0])
    dist_names = [
        "uniform",
        "norm",
        "gamma",
        "genlogistic",
    ]
    dist_results = []
    params = {}
    for dist_name in dist_names:
        dist = getattr(st, dist_name)
        param = dist.fit(data)

        params[dist_name] = param
        # Applying the Kolmogorov-Smirnov test
        _, p = st.kstest(data, dist_name, args=param)
        # print("p value for " + dist_name + " = " + str(p))
        dist_results.append((dist_name, p))

    # select the best fitted distribution
    best_dist, _ = max(dist_results, key=lambda item: item[1])
    # store the name of the best fit and its p value

    LOGGER.debug(
        "Best fitting distribution: %s%s", str(best_dist), str(params[best_dist])
    )
    # print("Best p value: " + str(best_p))

    return getattr(st, best_dist)(*params[best_dist])


def get_polls(
    dist: Any,
    upper_bound: float | None = None,
    worst_case_delta: float = 2.0,
    quality: float = 0.99,
    name: str = "_",
) -> list[float]:
    """Get polls based on distribution."""
    N = 1
    L = None
    upper_bound = upper_bound or dist.ppf(0.99)
    while True:
        L = _get_polling_interval(dist, N, upper_bound)
        valid = _examinate_2nd_derivate(dist, L)
        if not valid:
            LOGGER.warning("The result for %s is probably not minimized", name)
        valid = _examinate_delta(dist, L, worst_case_delta, quality)
        if valid:
            break
        N += 1
    return L


def _get_polling_interval(dist: Any, num_poll: int, upper_bound: float) -> list[float]:
    return _get_polling_interval_r(dist, num_poll, upper_bound, 0.0, upper_bound)


def _get_polling_interval_r(
    dist: Any,
    num_poll: int,
    upper_bound: float,
    left: float,
    right: float,
) -> list[float]:
    integral: Callable[[float, float], float] = lambda x, y: dist.cdf(y) - dist.cdf(x)
    L = [0.0 for _ in range(num_poll + 1)]
    # L0 is 0
    # randomized L1
    L[1] = (left + right) / 2
    if left == right:
        raise ValueError("left == right")
    too_large = False
    for n in range(2, num_poll + 1):
        L[n] = 1 / dist.pdf(L[n - 1]) * (integral(L[n - 2], L[n - 1])) + L[n - 1]
        if L[n] > upper_bound:
            too_large = True
            break
    if np.isclose(L[num_poll], upper_bound):
        L[num_poll] = upper_bound
        return L[1:]
    # L1 is too large
    if too_large:
        return _get_polling_interval_r(
            dist,
            num_poll,
            upper_bound,
            left,
            L[1],
        )
    # L1 is too small
    return _get_polling_interval_r(
        dist,
        num_poll,
        upper_bound,
        L[1],
        right,
    )


def _examinate_2nd_derivate(dist: Any, L: list[float]) -> bool:
    # examinate 2nd derivative
    pdf_prime = nd.Derivative(dist.pdf)
    for i, _ in enumerate(L):
        if i == len(L) - 1:
            return True
        val = 2 * dist.pdf(L[i]) - (L[i + 1] - L[i]) * pdf_prime(L[i])
        if val <= 0:
            return False
    return True


def _examinate_delta(
    dist: Any, L: list[float], worst_delta: float, quality: float
) -> bool:
    qouta = 1 - quality
    _max = 0.0
    L = [0.0] + L
    for i in range(1, len(L)):
        d = L[i] - L[i - 1]
        if d > _max:
            undetected = dist.cdf(L[i] - worst_delta) - dist.cdf(L[i - 1])
            if undetected > 0:
                qouta -= undetected
            if qouta < 0:
                _max = d
    return _max <= worst_delta
