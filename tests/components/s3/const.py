"""Consts for S3 tests."""

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
