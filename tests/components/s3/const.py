"""Consts for S3 tests."""

from homeassistant.components.s3.const import (
    CONF_ACCESS_KEY_ID,
    CONF_BUCKET,
    CONF_CHECKSUM_MODE,
    CONF_ENDPOINT_URL,
    CONF_SECRET_ACCESS_KEY,
    ChecksumMode,
)

USER_INPUT = {
    CONF_ACCESS_KEY_ID: "TestTestTestTestTest",
    CONF_SECRET_ACCESS_KEY: "TestTestTestTestTestTestTestTestTestTest",
    CONF_ENDPOINT_URL: "http://127.0.0.1:9000",
    CONF_BUCKET: "test",
}

EXPECTED_CONFIG_FLOW_DATA = {
    **USER_INPUT,
    # our mocks pretend that everything is fine for put_object
    CONF_CHECKSUM_MODE: ChecksumMode.WHEN_SUPPORTED,
}
