"""Consts for AWS S3 tests."""

from homeassistant.components.aws_s3.const import (
    CONF_ACCESS_KEY_ID,
    CONF_BUCKET,
    CONF_ENDPOINT_URL,
    CONF_SECRET_ACCESS_KEY,
    CONF_USE_DEFAULT_CREDENTIALS,
)
from homeassistant.const import CONF_PREFIX

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

# Credentials are resolved by Boto3, so no keys are stored
CONFIG_ENTRY_DATA_DEFAULT_CREDENTIALS = {
    CONF_USE_DEFAULT_CREDENTIALS: True,
    CONF_ENDPOINT_URL: "https://s3.eu-south-1.amazonaws.com",
    CONF_BUCKET: "test",
}

USER_INPUT_DEFAULT_CREDENTIALS = {
    **CONFIG_ENTRY_DATA_DEFAULT_CREDENTIALS,
    CONF_PREFIX: "",
}
