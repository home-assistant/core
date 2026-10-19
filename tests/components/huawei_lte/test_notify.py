"""Tests for the Huawei LTE notify platform."""

from unittest.mock import MagicMock, patch

from huawei_lte_api.exceptions import ResponseErrorException
import pytest

from homeassistant.components.huawei_lte.const import (
    DEFAULT_NOTIFY_SERVICE_NAME,
    DOMAIN,
)
from homeassistant.components.notify import (
    ATTR_MESSAGE,
    ATTR_TARGET,
    DOMAIN as NOTIFY_DOMAIN,
)
from homeassistant.const import CONF_RECIPIENT, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import magic_client

from tests.common import MockConfigEntry

MOCK_CONF_URL = "http://huawei-lte.example.com"

pytestmark = pytest.mark.parametrize(
    ("options", "service_data", "expected_targets"),
    [
        pytest.param(
            {},
            {ATTR_TARGET: ["+1234567890"]},
            ["+1234567890"],
            id="explicit_target",
        ),
        pytest.param(
            {CONF_RECIPIENT: ["+1234567890", "+0987654321"]},
            {},
            ["+1234567890", "+0987654321"],
            id="default_recipients",
        ),
    ],
)


async def setup_notify_service(
    hass: HomeAssistant, options: dict[str, list[str]]
) -> MagicMock:
    """Set up the integration and return the mocked router client."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_URL: MOCK_CONF_URL}, options=options
    )
    entry.add_to_hass(hass)
    client = magic_client()
    with (
        patch("homeassistant.components.huawei_lte.Connection", MagicMock()),
        patch("homeassistant.components.huawei_lte.Client", return_value=client),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.services.has_service(NOTIFY_DOMAIN, DEFAULT_NOTIFY_SERVICE_NAME)
    return client


async def test_send_message(
    hass: HomeAssistant,
    options: dict[str, list[str]],
    service_data: dict[str, list[str]],
    expected_targets: list[str],
) -> None:
    """Test that the message is sent to the given or the configured recipients."""
    client = await setup_notify_service(hass, options)

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        DEFAULT_NOTIFY_SERVICE_NAME,
        {ATTR_MESSAGE: "Hello", **service_data},
        blocking=True,
    )

    client.sms.send_sms.assert_called_once_with(
        phone_numbers=expected_targets, message="Hello"
    )


async def test_send_message_error(
    hass: HomeAssistant,
    options: dict[str, list[str]],
    service_data: dict[str, list[str]],
    expected_targets: list[str],
) -> None:
    """Test that a failing send raises an error with a translation key."""
    client = await setup_notify_service(hass, options)
    client.sms.send_sms.side_effect = ResponseErrorException("Send failed", 100)

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            DEFAULT_NOTIFY_SERVICE_NAME,
            {ATTR_MESSAGE: "Hello", **service_data},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "send_message_failed"
    assert exc_info.value.translation_placeholders == {
        "targets": ", ".join(expected_targets),
        "error": "Send failed",
    }
