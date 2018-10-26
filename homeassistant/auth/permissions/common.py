"""Common code for permissions."""
from typing import (  # noqa: F401
    Mapping, Union)

CategoryType = Union[Mapping[str, 'CategoryType'], bool, None]
PolicyType = Mapping[str, CategoryType]

SUBCAT_ALL = 'all'
