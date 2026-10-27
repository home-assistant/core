"""Utility functions for the KNX integration."""

from xknx.typing import DPTMainSubDict


def dpt_string_to_dict(dpt: str) -> DPTMainSubDict:
    """Convert a DPT string to a typed dictionary with main and sub components.

    Examples:
        >>> dpt_string_to_dict("1.010")
        {'main': 1, 'sub': 10}
        >>> dpt_string_to_dict("5")
        {'main': 5, 'sub': None}
    """
    dpt_num = dpt.split(".")
    return DPTMainSubDict(
        main=int(dpt_num[0]),
        sub=int(dpt_num[1]) if len(dpt_num) > 1 else None,
    )
