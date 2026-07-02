"""Exceptions used by the Scaleway Object Storage integration."""

import abc

from homeassistant.components.backup import BackupAgentError, BackupNotFound
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import CONF_BUCKET, CONF_SECTION_CREDENTIALS, DOMAIN


class ScalewayException(BackupAgentError, abc.ABC):
    """Base class for all exceptions raised by this integration."""

    def __init__(
        self,
        *,
        translation_key: str,
        translation_placeholders: dict[str, str] | None = None,
    ) -> None:
        """Initialize a new exception."""
        super().__init__(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders=translation_placeholders,
        )


class ScalewayConfigException(ScalewayException, abc.ABC):
    """Base class for all exceptions that might show up during the ConfigFlow."""

    def __init__(
        self,
        *,
        config_schema_key: str = "base",
        config_translation_key: str | None = None,
        translation_key: str,
        translation_placeholders: dict[str, str] | None = None,
    ) -> None:
        """Create a new ScalewayConfigException.

        Args:
            config_schema_key: the key within the config schema that this error is about in the context of a ConfigFlow.
            config_translation_key: the translation key (config.error.* in strings.json) in the context of a ConfigFlow. Defaults to translation_key.
            translation_key: the translation key (exceptions.* in strings.json)
            translation_placeholders: values to fill in for placeholders in the translation. Not applicable in the context of a ConfigFlow.
        """
        super().__init__(
            translation_key=translation_key,
            translation_placeholders=translation_placeholders,
        )
        self.config_schema_key = config_schema_key
        self.config_translation_key = config_translation_key or translation_key


class ScalewayConnectionError(ScalewayConfigException, ConfigEntryNotReady):
    """Raised if the network connection to Scaleway servers fails."""

    def __init__(self) -> None:
        """Initialize a new exception."""
        super().__init__(
            translation_key="cannot_connect",
        )


class ServerUnavailableError(ScalewayConfigException, ConfigEntryNotReady):
    """Raised if Scaleway services are temporarily unavailable."""

    def __init__(self) -> None:
        """Initialize a new exception."""
        super().__init__(translation_key="server_unavailable")


class UnsuccessfulResponseError(ScalewayConfigException):
    """Generic fallback for unexpected status code responses by Scaleway."""

    def __init__(self, status_code: int) -> None:
        """Initialize a new exception.

        Args:
            status_code: the response status code received from the Scaleway server
        """
        super().__init__(
            translation_key="unsuccessful_response",
            translation_placeholders={"status_code": str(status_code)},
        )


class InvalidBucketNameException(ScalewayConfigException):
    """Raised if the user provided an invalid bucket name."""

    def __init__(self) -> None:
        """Initialize a new exception."""
        super().__init__(
            translation_key="invalid_bucket_name",
            config_schema_key=CONF_BUCKET,
        )


class BucketNotFoundException(ScalewayConfigException):
    """Raised if the user configured a bucket that doesn't exist."""

    def __init__(self) -> None:
        """Initialize a new exception."""
        super().__init__(
            translation_key="bucket_not_found",
            config_schema_key=CONF_BUCKET,
        )


class ObjectNotFoundException(ScalewayException, BackupNotFound):
    """Raised if a specific backup object was requested but couldn't be found."""

    def __init__(self, *, object_key: str) -> None:
        """Initialize a new exception.

        Args:
            object_key: the object key that was requested but not found
        """
        super().__init__(
            translation_key="object_not_found",
            translation_placeholders={"object_key": object_key},
        )
        self.object_key = object_key


class MissingMetadataException(ScalewayException, BackupNotFound):
    """Raised if a backup object was found, but is missing the required metadata."""

    def __init__(self, *, object_key: str) -> None:
        """Initialize a new exception.

        Args:
            object_key: the key of the object that was requested but was missing metadata
        """
        super().__init__(
            translation_key="missing_object_metadata",
            translation_placeholders={"object_key": object_key},
        )


class InvalidAuthException(ScalewayConfigException, ConfigEntryAuthFailed):
    """Raised if the user-provided credentials are either invalid or have insufficient authorization."""

    def __init__(self) -> None:
        """Initialize a new exception."""
        super().__init__(
            translation_key="invalid_auth",
            config_schema_key=CONF_SECTION_CREDENTIALS,
        )
