"""Consts for S3 tests."""

from homeassistant.components.backup import AgentBackup
from homeassistant.components.s3.const import (
    CONF_ACCESS_KEY_ID,
    CONF_BUCKET,
    CONF_ENDPOINT_URL,
    CONF_SECRET_ACCESS_KEY,
)

USER_INPUT = {
    CONF_ACCESS_KEY_ID: "TestTestTestTestTest",
    CONF_SECRET_ACCESS_KEY: "TestTestTestTestTestTestTestTestTestTest",
    CONF_ENDPOINT_URL: "http://127.0.0.1:9000",
    CONF_BUCKET: "test",
}

TEST_BACKUP = AgentBackup(
    addons=[],
    backup_id="23e64aec",
    date="2024-11-22T11:48:48.727189+01:00",
    database_included=True,
    extra_metadata={},
    folders=[],
    homeassistant_included=True,
    homeassistant_version="2024.12.0.dev0",
    name="Core 2024.12.0.dev0",
    protected=False,
    size=34519040,
)
