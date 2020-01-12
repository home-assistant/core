"""Common code for permissions."""
from typing import Mapping, Union

# MyPy doesn't support recursion yet. So writing it out as far as we need.

ValueType = Union[
    # Example: entities.all = { read: true, control: true }
    Mapping[str, bool],
    bool,
    None,
]

# Example: entities.domains = { light: … }
SubCategoryDict = Mapping[str, ValueType]

SubCategoryType = Union[SubCategoryDict, bool, None]

CategoryType = Union[
    # Example: entities.domains
    Mapping[str, SubCategoryType],
    # Example: entities.all
    Mapping[str, ValueType],
    bool,
    None,
]

# Example: { entities: … }
PolicyType = Mapping[str, CategoryType]
