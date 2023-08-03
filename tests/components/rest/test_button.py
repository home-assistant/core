"""The tests for the REST button platform."""

import pytest

from homeassistant.components.button import (
    DOMAIN as BUTTON_DOMAIN,
    ButtonDeviceClass,
)
from homeassistant.components.rest import DOMAIN
from homeassistant.components.rest.button import CONF_BODY
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_HEADERS,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_RESOURCE,
    CONTENT_TYPE_JSON,
    STATE_OFF,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component

NAME = "foo"
DEVICE_CLASS = ButtonDeviceClass.IDENTIFY
RESOURCE = "http://localhost/"


async def test_setup_missing_config(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test setup with configuration missing required entries."""
    config = {BUTTON_DOMAIN: {CONF_PLATFORM: DOMAIN}}
    assert await async_setup_component(hass, BUTTON_DOMAIN, config)
    await hass.async_block_till_done()
    assert_setup_component(0, BUTTON_DOMAIN)
    assert "Invalid config for [button.rest]: required key not provided" in caplog.text


async def test_setup_missing_schema(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test setup with resource missing schema."""
    config = {BUTTON_DOMAIN: {CONF_PLATFORM: DOMAIN, CONF_RESOURCE: "localhost"}}
    assert await async_setup_component(hass, BUTTON_DOMAIN, config)
    await hass.async_block_till_done()
    assert_setup_component(0, BUTTON_DOMAIN)
    assert "Invalid config for [button.rest]: invalid url" in caplog.text


async def test_setup(hass: HomeAssistant) -> None:
    """Test setup with valid configuration."""
    config = {
        BUTTON_DOMAIN: {
            CONF_PLATFORM: DOMAIN,
            CONF_NAME: "foo",
            CONF_RESOURCE: RESOURCE,
            CONF_HEADERS: {"Content-type": CONTENT_TYPE_JSON},
            CONF_BODY: "custom on text",
        }
    }
    assert await async_setup_component(hass, BUTTON_DOMAIN, config)
    await hass.async_block_till_done()
    assert_setup_component(1, BUTTON_DOMAIN)


# Tests for REST button platform.


async def _async_setup_test_button(hass: HomeAssistant) -> None:
    headers = {"Content-type": CONTENT_TYPE_JSON}
    config = {
        CONF_PLATFORM: DOMAIN,
        CONF_NAME: NAME,
        CONF_DEVICE_CLASS: DEVICE_CLASS,
        CONF_RESOURCE: RESOURCE,
        CONF_HEADERS: headers,
    }
    assert await async_setup_component(hass, BUTTON_DOMAIN, {BUTTON_DOMAIN: config})
    await hass.async_block_till_done()
    assert_setup_component(1, BUTTON_DOMAIN)

    assert hass.states.get("button.foo").state == STATE_OFF
