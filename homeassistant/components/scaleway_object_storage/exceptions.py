"""Exceptions used by the Scaleway Object Storage integration."""

from typing import final

from homeassistant.components.backup import BackupAgentError

from .const import DOMAIN


class ScalewayBackupException(BackupAgentError):
    """Base class for all exceptions raised by this integration."""

    translation_key: str

    def __init__(
        self,
        *,
        translation_domain: str = DOMAIN,
        translation_key: str,
        translation_placeholders: dict[str, str] | None = None,
    ) -> None:
        """Initialize a new exception."""
        super().__init__(
            translation_domain=translation_domain,
            translation_key=translation_key,
            translation_placeholders=translation_placeholders,
        )


@final
class ScalewayNotReadyException(ScalewayBackupException):
    """Raised if communication with Scaleway is currently not possible (connection errors, service unavailable, etc.)."""


@final
class InvalidBucketException(ScalewayBackupException):
    """Raised if the user configured an invalid bucket."""
