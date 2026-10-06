"""Helpers to translate OSError from file operations."""

import errno

# Integrations reference the matching common::exceptions messages in strings.json
OS_ERROR_TRANSLATION_KEYS: dict[int | None, str] = {
    errno.EACCES: "os_error_permission_denied",
    errno.EPERM: "os_error_permission_denied",
    errno.ENOSPC: "os_error_no_space",
    errno.EROFS: "os_error_read_only",
    errno.ENOENT: "os_error_not_found",
}


def os_error_translation_key(err: OSError) -> str:
    """Return the translation key for an OSError, os_error if it has no own key."""
    return OS_ERROR_TRANSLATION_KEYS.get(err.errno, "os_error")
