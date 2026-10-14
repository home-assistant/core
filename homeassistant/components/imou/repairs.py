"""Repairs for Imou."""

from pyimouapi.exceptions import ImouException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import CONF_API_URL, DOMAIN

ISSUE_OPEN_API_QUOTA = "open_api_quota_exceeded"

_QUOTA_CODE = "OP1013"
_RESOURCES_CN = "https://open.imou.com/consoleNew/resourceManage/myResource"
_RESOURCES_OVERSEAS = "https://open.imoulife.com/consoleNew/resourceManage/myResource"


def _issue_id(key: str, entry_id: str) -> str:
    return f"{key}_{entry_id}"


def is_quota_exceeded(error: BaseException) -> bool:
    """Return True when the Open Platform monthly call limit is used up."""
    if isinstance(error, ImouException):
        text = getattr(error, "message", None) or str(error)
        return _QUOTA_CODE in str(text).upper()
    return _QUOTA_CODE in str(error).upper()


def _quota_learn_more_url(entry: ConfigEntry) -> str:
    if entry.data.get(CONF_API_URL) == "cn":
        return _RESOURCES_CN
    return _RESOURCES_OVERSEAS


@callback
def async_create_quota_exceeded_issue(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Explain that the App ID has no Open Platform calls left this month."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        _issue_id(ISSUE_OPEN_API_QUOTA, entry.entry_id),
        config_entry_id=entry.entry_id,
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key=ISSUE_OPEN_API_QUOTA,
        learn_more_url=_quota_learn_more_url(entry),
    )


@callback
def async_notify_imou_api_error(
    hass: HomeAssistant, entry: ConfigEntry, error: BaseException
) -> None:
    """Create the quota repair when the cloud refuses the call for that reason."""
    if is_quota_exceeded(error):
        async_create_quota_exceeded_issue(hass, entry)


@callback
def async_delete_quota_issue(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Clear the quota repair after calls succeed again."""
    ir.async_delete_issue(hass, DOMAIN, _issue_id(ISSUE_OPEN_API_QUOTA, entry.entry_id))
