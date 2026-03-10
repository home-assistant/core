"""Consts for Backblaze B2 tests."""

from homeassistant.components.backblaze_b2.const import CONF_BUCKET, CONF_PREFIX
from homeassistant.components.backup import AgentBackup

USER_INPUT = {
    CONF_BUCKET: "testBucket",
    CONF_PREFIX: "testprefix/",
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
    size=48,
)

BACKUP_METADATA = {
    "metadata_version": "1",
    "backup_id": "23e64aec",
    "backup_metadata": TEST_BACKUP.as_dict(),
}

METADATA_FILE_SUFFIX = ".metadata.json"
