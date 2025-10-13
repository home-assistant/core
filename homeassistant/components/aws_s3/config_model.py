"""Configuration model for AWS S3 integration.

This module defines S3ConfigModel, which manages configuration state, authentication modes,
and error tracking for the configuration of the AWS S3 Home Assistant integration.
"""

from collections.abc import MutableMapping

from aiobotocore.session import AioSession
from botocore.exceptions import (
    ClientError,
    ConnectionError,
    NoCredentialsError,
    ParamValidationError,
    ProfileNotFound,
    TokenRetrievalError,
)

from .const import (
    CONF_ACCESS_KEY_ID,
    CONF_AUTH_MODE,
    CONF_AUTH_MODE_EXPLICIT,
    CONF_AUTH_MODE_IMPLICIT,
    CONF_AUTH_MODE_PROFILE,
    CONF_BUCKET,
    CONF_ENDPOINT_URL,
    CONF_PROFILE_NAME,
    CONF_SECRET_ACCESS_KEY,
)


class S3ConfigModel(MutableMapping[str, str]):
    """Configuration model for AWS S3 integration, supporting multiple authentication modes and error tracking."""

    _AuthModeBlanks = {
        None: {CONF_PROFILE_NAME},
        CONF_AUTH_MODE_EXPLICIT: {CONF_PROFILE_NAME},
        CONF_AUTH_MODE_IMPLICIT: {
            CONF_PROFILE_NAME,
            CONF_ACCESS_KEY_ID,
            CONF_SECRET_ACCESS_KEY,
        },
        CONF_AUTH_MODE_PROFILE: {CONF_ACCESS_KEY_ID, CONF_SECRET_ACCESS_KEY},
    }

    def __init__(self) -> None:
        """Initialize the S3ConfigModel with the given flow ID and default values."""
        self._data: dict[str, str] = {}
        self[CONF_BUCKET] = None
        self[CONF_ENDPOINT_URL] = None
        self[CONF_AUTH_MODE] = None
        self[CONF_PROFILE_NAME] = None
        self[CONF_ACCESS_KEY_ID] = None
        self[CONF_SECRET_ACCESS_KEY] = None
        self._errors: dict[str, str] = {}
        super().__init__()

    def as_dict(self, only: None | set[str] = None) -> dict[str, str]:
        """Return a dictionary representation of the config.

        Args:
            only: An optional set of keys to include in the result. If None, include all keys.

        Returns:
             A dictionary containing the selected configuration items.
        """
        if only is None:
            return dict(self.items())

        return {k: v for k, v in self.items() if k in only}

    def from_dict(self, data: dict[str, str]) -> None:
        """Update the configuration from a dictionary.

        Args:
            data: A dictionary containing configuration values to update.
        """
        for k in self.keys():
            if k in data:
                self[k] = data[k]

    def __setitem__(self, key, value):
        """Set a configuration value, handling blanking for auth mode changes."""
        if key == CONF_AUTH_MODE:
            if self[CONF_AUTH_MODE] != value and value in S3ConfigModel._AuthModeBlanks:
                self._blank(S3ConfigModel._AuthModeBlanks[value])
        self._data[key] = value

    def __getitem__(self, key):
        """Return the value for the given configuration key."""
        return self._data.get(key)

    def __delitem__(self, key):
        """Delete a configuration item by key."""
        return self._data.__delitem__(key)

    def __iter__(self):
        """Return an iterator over the configuration keys."""
        return self._data.__iter__()

    def __len__(self):
        """Return the number of configuration items."""
        return len(self._data)

    def _blank(self, blank: set[str]) -> None:
        for i in blank:
            if i in self:
                self[i] = None

    async def async_validate_access(self) -> None:
        """Test the connection to the bucket."""
        self._errors.clear()
        try:
            session = AioSession(profile=self[CONF_PROFILE_NAME])
            async with session.create_client(
                "s3",
                endpoint_url=self[CONF_ENDPOINT_URL],
                aws_secret_access_key=self[CONF_SECRET_ACCESS_KEY],
                aws_access_key_id=self[CONF_ACCESS_KEY_ID],
            ) as client:
                await client.head_bucket(Bucket=self[CONF_BUCKET])
        except NoCredentialsError:
            self.record_error_missing_credentials()
        except ProfileNotFound:
            self.record_error_missing_credentials()
        except ClientError:
            self.record_error_invalid_credentials()
        except TokenRetrievalError:
            self.record_error_invalid_credentials()
        except ParamValidationError as err:
            if "Invalid bucket name" in str(err):
                self.record_error(CONF_BUCKET, "invalid_bucket_name")
        except ValueError:
            self.record_error(CONF_ENDPOINT_URL, "invalid_endpoint_url")
        except ConnectionError:
            self.record_error(CONF_ENDPOINT_URL, "cannot_connect")

    def record_error_missing_credentials(self) -> None:
        """Record an error for missing credentials based on the current authentication mode."""
        if self[CONF_AUTH_MODE] == CONF_AUTH_MODE_IMPLICIT:
            self.record_error(CONF_AUTH_MODE, "no_credentials_implicit")
        elif self[CONF_AUTH_MODE] == CONF_AUTH_MODE_PROFILE:
            self.record_error(CONF_PROFILE_NAME, "no_credentials_profile")
        elif self[CONF_AUTH_MODE] == CONF_AUTH_MODE_EXPLICIT:
            self.record_error(CONF_ACCESS_KEY_ID, "invalid_credentials_explicit")
            self.record_error(CONF_SECRET_ACCESS_KEY, "invalid_credentials_explicit")

    def record_error_invalid_credentials(self) -> None:
        """Record an error for invalid credentials based on the current authentication mode."""
        if self[CONF_AUTH_MODE] == CONF_AUTH_MODE_IMPLICIT:
            self.record_error(CONF_AUTH_MODE, "invalid_credentials")
        elif self[CONF_AUTH_MODE] == CONF_AUTH_MODE_PROFILE:
            self.record_error(CONF_PROFILE_NAME, "invalid_credentials")
        elif self[CONF_AUTH_MODE] == CONF_AUTH_MODE_EXPLICIT:
            self.record_error(CONF_ACCESS_KEY_ID, "invalid_credentials_explicit")
            self.record_error(CONF_SECRET_ACCESS_KEY, "invalid_credentials_explicit")

    def record_error(self, error_context: str, error_identifier: str) -> None:
        """Record an error for a specific context with the given identifier.

        Args:
            error_context: The configuration key or context where the error occurred.
            error_identifier: The error code or identifier describing the error.
        """
        self._errors[error_context] = error_identifier

    def has_errors(self, keys: set[str]) -> bool:
        """Return True if any of the specified keys have recorded errors.

        Args:
            keys: A set of configuration keys to check for errors.

        Returns:
            True if any of the specified keys have errors, False otherwise.
        """
        return len(keys.intersection(self._errors.keys())) > 0

    def get_errors(self) -> dict[str, str]:
        """Return and clear all recorded errors.

        Returns:
            A dictionary mapping error contexts to error identifiers.
        """
        error_list = dict(self._errors.items())
        self._errors.clear()
        return error_list

    def filter_errors(self, keys: set[str]) -> None:
        """Filter the recorded errors to only include those for the specified keys.

        Args:
            keys: A set of configuration keys to retain errors for.
        """
        error_list = {k: v for k, v in self._errors.items() if k in keys}
        self._errors = error_list
