"""Configuration model for AWS S3 integration.

This module defines S3ConfigModel, which manages configuration state, authentication modes,
and error tracking for the configuration of the AWS S3 Home Assistant integration.
"""

from collections.abc import MutableMapping

from .const import (
    CONF_ACCESS_KEY_ID,
    CONF_BUCKET,
    CONF_ENDPOINT_URL,
    CONF_SECRET_ACCESS_KEY,
)


class S3ConfigModel(MutableMapping[str, str]):
    """Configuration model for AWS S3 integration, supporting multiple authentication modes and error tracking."""

    def __init__(self) -> None:
        """Initialize the S3ConfigModel with the given flow ID and default values."""
        self._data: dict[str, str] = {}
        self[CONF_BUCKET] = None
        self[CONF_ENDPOINT_URL] = None
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
        """Set the value for the given configuration key."""
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
