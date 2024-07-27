"""The constants for evohome tests."""

from typing import Final

from homeassistant.components.evohome import dt_aware_to_naive
import homeassistant.util.dt as dt_util

USERNAME_DIFF: Final = "diff_user@email.com"
USERNAME_SAME: Final = "same_user@email.com"

REFRESH_TOKEN: Final = "jg68ZCKYdxEI3fF..."
ACCESS_TOKEN: Final = "1dc7z657UKzbhKA..."

ACCESS_TOKEN_EXP_TZ: Final = dt_util.UTC
ACCESS_TOKEN_EXP_STR: Final = "2024-06-10T22:05:54+00:00"
ACCESS_TOKEN_EXP_DTM: Final = dt_aware_to_naive(
    dt_util.parse_datetime(ACCESS_TOKEN_EXP_STR)  # type: ignore[arg-type]
)

SESSION_ID: Final = "F7181186..."
