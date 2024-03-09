"""Test the HTML5 config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.html5.const import (
    ATTR_VAPID_EMAIL,
    ATTR_VAPID_PRV_KEY,
    ATTR_VAPID_PUB_KEY,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

MOCK_CONF = {
    ATTR_VAPID_EMAIL: "test@example.com",
    ATTR_VAPID_PRV_KEY: "h6acSRds8_KR8hT9djD8WucTL06Gfe29XXyZ1KcUjN8",
}
MOCK_CONF_PUB_KEY = "BIUtPN7Rq_8U7RBEqClZrfZ5dR9zPCfvxYPtLpWtRVZTJEc7lzv2dhzDU6Aw1m29Ao0-UA1Uq6XO9Df8KALBKqA"


async def test_step_user_success(hass: HomeAssistant) -> None:
    """Test a successful user config flow."""

    with patch(
        "homeassistant.components.html5.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=MOCK_CONF
        )

        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["data"] == {
            ATTR_VAPID_PRV_KEY: MOCK_CONF[ATTR_VAPID_PRV_KEY],
            ATTR_VAPID_PUB_KEY: MOCK_CONF_PUB_KEY,
            ATTR_VAPID_EMAIL: MOCK_CONF[ATTR_VAPID_EMAIL],
        }

        assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("key", "value"),
    [
        (ATTR_VAPID_EMAIL, "invalid"),
        (ATTR_VAPID_PRV_KEY, "invalid"),
    ],
)
async def test_step_user_form(hass: HomeAssistant, key: str, value: str) -> None:
    """Test invalid user input."""

    with patch(
        "homeassistant.components.html5.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        bad_conf = MOCK_CONF.copy()
        bad_conf[key] = value

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=bad_conf
        )

        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert len(mock_setup_entry.mock_calls) == 0


async def test_step_import_good(hass: HomeAssistant) -> None:
    """Test valid import input."""

    with patch(
        "homeassistant.components.html5.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        conf = MOCK_CONF.copy()
        conf[ATTR_VAPID_PUB_KEY] = MOCK_CONF_PUB_KEY
        conf["random_key"] = "random_value"

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=conf
        )

        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["data"] == {
            ATTR_VAPID_PRV_KEY: conf[ATTR_VAPID_PRV_KEY],
            ATTR_VAPID_PUB_KEY: MOCK_CONF_PUB_KEY,
            ATTR_VAPID_EMAIL: conf[ATTR_VAPID_EMAIL],
        }

        assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("key", "value"),
    [
        (ATTR_VAPID_EMAIL, "invalid"),
        (ATTR_VAPID_PRV_KEY, "invalid"),
    ],
)
async def test_step_import_bad(hass: HomeAssistant, key: str, value: str) -> None:
    """Test invalid import input."""

    with patch(
        "homeassistant.components.html5.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        bad_conf = MOCK_CONF.copy()
        bad_conf[key] = value

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=bad_conf
        )

        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert len(mock_setup_entry.mock_calls) == 0
