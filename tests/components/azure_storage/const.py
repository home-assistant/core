"""Consts for Azure Storage tests."""

from homeassistant.components.azure_storage.const import (
    CONF_ACCOUNT_NAME,
    CONF_CONTAINER_NAME,
    CONF_STORAGE_ACCOUNT_KEY,
)

USER_INPUT = {
    CONF_ACCOUNT_NAME: "account",
    CONF_CONTAINER_NAME: "container1",
    CONF_STORAGE_ACCOUNT_KEY: "test",
}

BACKUP_METADATA = {
    "addons": "",
    "backup_id": "23e64aec",
    "date": "2024-11-22T11:48:48.727189+01:00",
    "database_included": "True",
    "extra_metadata": "",
    "folders": "",
    "homeassistant_included": "True",
    "homeassistant_version": "2024.12.0.dev0",
    "name": "Core 2024.12.0.dev0",
    "protected": "False",
    "size": "34519040",
}
