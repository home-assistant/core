"""Consts for AWS S3 tests."""

from homeassistant.components.aws_s3.const import (
    CONF_ACCESS_KEY_ID,
    CONF_BUCKET,
    CONF_ENDPOINT_URL,
    CONF_PREFIX,
    CONF_SECRET_ACCESS_KEY,
)

# What gets persisted in the config entry (empty prefix is not stored)
CONFIG_ENTRY_DATA = {
    CONF_ACCESS_KEY_ID: "TestTestTestTestTest",
    CONF_SECRET_ACCESS_KEY: "TestTestTestTestTestTestTestTestTestTest",
    CONF_ENDPOINT_URL: "https://s3.eu-south-1.amazonaws.com",
    CONF_BUCKET: "test",
}

# What users submit to the flow (can include empty prefix)
USER_INPUT = {
    **CONFIG_ENTRY_DATA,
    CONF_PREFIX: "",
}
