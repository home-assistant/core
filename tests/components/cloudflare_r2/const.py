"""Consts for Cloudflare R2 tests."""

from homeassistant.components.cloudflare_r2.const import (
    CONF_ACCESS_KEY_ID,
    CONF_BUCKET,
    CONF_ENDPOINT_URL,
    CONF_SECRET_ACCESS_KEY,
)

USER_INPUT = {
    CONF_ACCESS_KEY_ID: "R2AccessKeyIdExample",
    CONF_SECRET_ACCESS_KEY: "R2SecretAccessKeyExampleExample",
    CONF_ENDPOINT_URL: "https://1234567890abcdef.r2.cloudflarestorage.com",
    CONF_BUCKET: "test",
}
