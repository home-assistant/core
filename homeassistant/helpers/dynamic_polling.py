"""Dynamic polling helper."""
from __future__ import annotations

from collections.abc import Callable
from logging import getLogger
import math
from typing import Any

import numdifftools as nd
import numpy as np
import scipy.stats as st

LOGGER = getLogger(__name__)

dist_list = [
    "alpha",
    "anglit",
    "arcsine",
    "argus",
    "beta",
    "betaprime",
    "bradford",
    "burr",
    "burr12",
    "cauchy",
    "chi",
    "chi2",
    "cosine",
    "crystalball",
    "dgamma",
    "dweibull",
    "erlang",
    "expon",
    "exponnorm",
    "exponweib",
    "exponpow",
    "f",
    "fatiguelife",
    "fisk",
    "foldcauchy",
    "foldnorm",
    "genlogistic",
    "gennorm",
    "genpareto",
    "genexpon",
    "genextreme",
    "gausshyper",
    "gamma",
    "gengamma",
    "genhalflogistic",
    "genhyperbolic",
    "geninvgauss",
    "gibrat",
    "gompertz",
    "gumbel_r",
    "gumbel_l",
    "halfcauchy",
    "halflogistic",
    "halfnorm",
    "halfgennorm",
    "hypsecant",
    "invgamma",
    "invgauss",
    "invweibull",
    "jf_skew_t",
    "johnsonsb",
    "johnsonsu",
    "kappa4",
    "kappa3",
    "ksone",
    "kstwo",
    "kstwobign",
    "laplace",
    "laplace_asymmetric",
    "levy",
    "levy_l",
    "levy_stable",
    "logistic",
    "loggamma",
    "loglaplace",
    "lognorm",
    "loguniform",
    "lomax",
    "maxwell",
    "mielke",
    "moyal",
    "nakagami",
    "ncx2",
    "ncf",
    "nct",
    "norm",
    "norminvgauss",
    "pareto",
    "pearson3",
    "powerlaw",
    "powerlognorm",
    "powernorm",
    "rdist",
    "rayleigh",
    "rel_breitwigner",
    "rice",
    "recipinvgauss",
    "semicircular",
    "skewcauchy",
    "skewnorm",
    "studentized_range",
    "t",
    "trapezoid",
    "triang",
    "truncexpon",
    "truncnorm",
    "truncpareto",
    "truncweibull_min",
    "tukeylambda",
    "uniform",
    "vonmises",
    "vonmises_line",
    "wald",
    "weibull_min",
    "weibull_max",
    "wrapcauchy",
]


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
    # dist_names = dist_list
    dist_results = []
    params = {}
    for dist_name in dist_names:
        dist = getattr(st, dist_name)
        param = dist.fit(data)

        params[dist_name] = param
        # Applying the Kolmogorov-Smirnov test
        _, p = st.kstest(data, dist_name, args=param)
        dist_results.append((dist_name, p))

    # select the best fitted distribution
    best_dist, _ = max(dist_results, key=lambda item: item[1])
    # store the name of the best fit and its p value

    LOGGER.debug(
        "Best fitting distribution: %s%s", str(best_dist), str(params[best_dist])
    )
    # print("Best p value: " + str(best_p))
    # print(params[best_dist])

    return getattr(st, best_dist)(*params[best_dist])


def _get_polling_interval(dist: Any, num_poll: int, upper_bound: float) -> list[float]:
    return _get_polling_interval_r(dist, num_poll, upper_bound, 0, upper_bound)


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
    L[0] = 0.0
    L[1] = (left + right) / 2
    if left == right:
        raise ValueError("left == right")
    too_large = -1
    for n in range(2, num_poll + 1):
        if dist.pdf(L[n - 1]) == 0 and dist.cdf(L[n - 1]) == 0:
            break
        L[n] = 1 / dist.pdf(L[n - 1]) * (integral(L[n - 2], L[n - 1])) + L[n - 1]
        if L[n] > upper_bound:
            too_large = n
            break

    if np.isclose(L[num_poll], upper_bound):
        L[num_poll] = upper_bound
        return L[1:]

    # L1 is too large
    if too_large != -1:
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


def _examinate_Q(dist: Any, L: list[float]) -> float:
    L = [0] + L
    Q = 0
    for i in range(1, len(L)):
        Q += L[i] * (dist.cdf(L[i]) - dist.cdf(L[i - 1]))
    Q -= dist.expect(lambda x: x, lb=0.0, ub=L[-1])
    # print(f"Q = {round(Q, 2)}, k = {len(L)-1}")
    return Q


def _examinate_delta(
    dist: Any, L: list[float], delta: float, SLO: float = 0.95
) -> bool:
    L = [0] + L
    prob = 0
    for i in range(1, len(L)):
        prob += dist.cdf(L[i]) - dist.cdf(max(L[i - 1], L[i] - delta))

    return prob >= float(SLO - dist.cdf(0))


def get_detection_time(dist: Any, L: list[float]) -> float:
    """Get detection time of L."""
    return _examinate_Q(dist, L)


def get_polls(
    dist: Any,
    *,
    upper_bound: float | None = None,
    worst_case_delta: float = 2.0,
    SLO: float = 0.95,
    name: str = "_",
    N: int | None = None,
) -> list[float]:
    """Get polls based on distribution."""
    upper_bound = upper_bound or float(dist.ppf(0.99))
    if N is not None:
        L = _get_polling_interval(dist, N, upper_bound)
        valid = _examinate_2nd_derivate(dist, L)
        if not valid:
            print("The result for", name, "is probably not minimized.")  # noqa: T201

        return L

    return _r_get_polls(
        dist,
        upper_bound,
        0,
        math.ceil(upper_bound / worst_case_delta),
        -1,
        worst_case_delta,
        SLO,
        name,
    )


def _r_get_polls(
    dist: Any,
    upper_bound: float,
    left_N: int,
    right_N: int,
    last_N: int,
    worst_case_delta: float = 2.0,
    SLO: float = 0.95,
    name: str = "_",
) -> list[float]:
    N = max(1, math.floor((left_N + right_N) / 2))
    # print(N)
    try:
        L = _get_polling_interval(dist, N, upper_bound)
    except ValueError:
        return _r_get_polls(
            dist, upper_bound, left_N, N + 1, N, worst_case_delta, SLO, name
        )
    valid = _examinate_2nd_derivate(dist, L)
    if not valid:
        print("The result for", name, "is probably not minimized.")  # noqa: T201

    # _examinate_Q(dist, L, SLO)
    valid = _examinate_delta(dist, L, worst_case_delta, SLO)

    if left_N == right_N or last_N == N:
        if not valid:
            raise ValueError("Failed to find the polls")
        return L

    if valid:
        # want to further reduce polls
        return _r_get_polls(
            dist, upper_bound, left_N, N + 1, N, worst_case_delta, SLO, name
        )
    if N + 1 >= right_N:
        return _r_get_polls(
            dist, upper_bound, N + 1, right_N * 2, N, worst_case_delta, SLO, name
        )
    return _r_get_polls(
        dist, upper_bound, N + 1, right_N, N, worst_case_delta, SLO, name
    )


def get_uniform_polls(
    upper_bound: float, *, N: int | None = None, worst_case_delta: float = 2.0
) -> list[float]:
    """Get uniform polls."""
    if N is not None:
        return [(i + 1) * upper_bound / N for i in range(N)]
    polls = [
        (i + 1) * worst_case_delta
        for i in range(math.floor(upper_bound / worst_case_delta))
    ]
    if not np.isclose(polls[-1], upper_bound):
        polls.append(upper_bound)
    return polls
