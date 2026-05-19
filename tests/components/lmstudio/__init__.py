"""Tests for the LM Studio integration."""

from homeassistant.components.lmstudio import const
from homeassistant.const import CONF_API_KEY, CONF_URL

TEST_USER_DATA = {
    CONF_URL: "http://localhost:1234",
    CONF_API_KEY: "test-api-key",
}

TEST_OPTIONS = {
    const.CONF_MODEL: "test-model",
    const.CONF_PROMPT: "You are helpful.",
    const.CONF_MAX_HISTORY: 3,
    const.CONF_TEMPERATURE: 0.4,
}

TEST_AI_TASK_OPTIONS = {
    const.CONF_MODEL: "test-model",
}
