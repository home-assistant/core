"""Helpers to raise translated errors for failed file operations."""

import errno

from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

# OS error texts aren't translatable, so the common causes get their own message
_WRITE_ERROR_TRANSLATION_KEYS: dict[int | None, str] = {
    errno.EACCES: "os_write_permission_denied",
    errno.EPERM: "os_write_permission_denied",
    errno.ENOSPC: "os_write_no_space",
    errno.EROFS: "os_write_read_only",
    errno.ENOENT: "os_write_dir_not_found",
}
_READ_ERROR_TRANSLATION_KEYS: dict[int | None, str] = {
    errno.EACCES: "os_read_permission_denied",
    errno.EPERM: "os_read_permission_denied",
    errno.EISDIR: "os_read_is_directory",
}


def os_write_error(err: OSError, path: str) -> HomeAssistantError:
    """Return a translated error for an OSError raised while writing path."""
    return HomeAssistantError(
        translation_domain=HOMEASSISTANT_DOMAIN,
        translation_key=_WRITE_ERROR_TRANSLATION_KEYS.get(err.errno, "os_write_error"),
        translation_placeholders={"path": path},
    )


def os_read_error(err: OSError, path: str) -> HomeAssistantError:
    """Return a translated error for an OSError raised while reading path."""
    # A missing file is usually a wrong path given by the user
    if err.errno == errno.ENOENT:
        return ServiceValidationError(
            translation_domain=HOMEASSISTANT_DOMAIN,
            translation_key="os_read_not_found",
            translation_placeholders={"path": path},
        )
    return HomeAssistantError(
        translation_domain=HOMEASSISTANT_DOMAIN,
        translation_key=_READ_ERROR_TRANSLATION_KEYS.get(err.errno, "os_read_error"),
        translation_placeholders={"path": path},
    )
