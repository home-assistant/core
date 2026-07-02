"""Tests for the Huawei LTE SMS services."""

from unittest.mock import MagicMock, patch

from huawei_lte_api.exceptions import ResponseErrorException
import pytest

from homeassistant.components.huawei_lte.const import (
    DOMAIN,
    SERVICE_DELETE_SMS,
    SERVICE_GET_SMS_LIST,
    SERVICE_MARK_SMS_READ,
)
from homeassistant.const import ATTR_CONFIG_ENTRY_ID, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from . import magic_client

from tests.common import MockConfigEntry

MOCK_CONF_URL = "http://huawei-lte.example.com"


async def _setup_integration(
    hass: HomeAssistant,
) -> tuple[MockConfigEntry, MagicMock]:
    """Set up the integration with a mock client."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_URL: MOCK_CONF_URL})
    entry.add_to_hass(hass)
    client = magic_client()
    with (
        patch("homeassistant.components.huawei_lte.Connection", MagicMock()),
        patch("homeassistant.components.huawei_lte.Client", return_value=client),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, client


async def test_get_sms_list(hass: HomeAssistant) -> None:
    """Test get_sms_list service returns messages."""
    entry, client = await _setup_integration(hass)

    client.sms.get_sms_list.reset_mock()

    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_SMS_LIST,
        {ATTR_CONFIG_ENTRY_ID: entry.entry_id},
        blocking=True,
        return_response=True,
    )
    client.sms.get_sms_list.assert_called_once()
    assert "messages" in result
    assert len(result["messages"]) == 2
    assert result["messages"][0]["phone"] == "+1234567890"
    assert result["messages"][0]["content"] == "Test message 1"
    assert result["messages"][0]["index"] == 40001
    assert result["messages"][0]["read"] is False
    assert result["messages"][1]["read"] is True


async def test_get_sms_list_with_params(hass: HomeAssistant) -> None:
    """Test get_sms_list service with page and count parameters."""
    entry, client = await _setup_integration(hass)

    client.sms.get_sms_list.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_SMS_LIST,
        {ATTR_CONFIG_ENTRY_ID: entry.entry_id, "page": 2, "count": 10},
        blocking=True,
        return_response=True,
    )
    args = client.sms.get_sms_list.call_args
    assert args[0][0] == 2  # page
    assert args[0][2] == 10  # count


async def test_delete_sms(hass: HomeAssistant) -> None:
    """Test delete_sms service calls the API."""
    entry, client = await _setup_integration(hass)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_DELETE_SMS,
        {ATTR_CONFIG_ENTRY_ID: entry.entry_id, "index": 40001},
        blocking=True,
    )
    client.sms.delete_sms.assert_called_once_with(40001)


async def test_mark_sms_read(hass: HomeAssistant) -> None:
    """Test mark_sms_read service calls the API."""
    entry, client = await _setup_integration(hass)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_MARK_SMS_READ,
        {ATTR_CONFIG_ENTRY_ID: entry.entry_id, "index": 40001},
        blocking=True,
    )
    client.sms.set_read.assert_called_once_with(40001)


async def test_get_sms_list_wrong_entry_id(hass: HomeAssistant) -> None:
    """Test get_sms_list raises HomeAssistantError for unknown entry ID."""
    await _setup_integration(hass)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_SMS_LIST,
            {ATTR_CONFIG_ENTRY_ID: "nonexistent_entry"},
            blocking=True,
            return_response=True,
        )


async def test_get_sms_list_suspended(hass: HomeAssistant) -> None:
    """Test get_sms_list raises ServiceValidationError when router is suspended."""
    entry, client = await _setup_integration(hass)

    router = hass.data[DOMAIN].routers[entry.entry_id]
    router.suspended = True

    client.sms.get_sms_list.reset_mock()
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_SMS_LIST,
            {ATTR_CONFIG_ENTRY_ID: entry.entry_id},
            blocking=True,
            return_response=True,
        )
    client.sms.get_sms_list.assert_not_called()


async def test_delete_sms_suspended(hass: HomeAssistant) -> None:
    """Test delete_sms raises ServiceValidationError when router is suspended."""
    entry, client = await _setup_integration(hass)

    router = hass.data[DOMAIN].routers[entry.entry_id]
    router.suspended = True

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DELETE_SMS,
            {ATTR_CONFIG_ENTRY_ID: entry.entry_id, "index": 40001},
            blocking=True,
        )
    client.sms.delete_sms.assert_not_called()


async def test_mark_sms_read_suspended(hass: HomeAssistant) -> None:
    """Test mark_sms_read raises ServiceValidationError when router is suspended."""
    entry, client = await _setup_integration(hass)

    router = hass.data[DOMAIN].routers[entry.entry_id]
    router.suspended = True

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_MARK_SMS_READ,
            {ATTR_CONFIG_ENTRY_ID: entry.entry_id, "index": 40001},
            blocking=True,
        )
    client.sms.set_read.assert_not_called()


async def test_get_sms_list_empty_response(hass: HomeAssistant) -> None:
    """Test get_sms_list handles empty Messages."""
    entry, client = await _setup_integration(hass)

    client.sms.get_sms_list.reset_mock()
    client.sms.get_sms_list.return_value = {"Count": "0", "Messages": None}

    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_SMS_LIST,
        {ATTR_CONFIG_ENTRY_ID: entry.entry_id},
        blocking=True,
        return_response=True,
    )
    assert result == {"messages": []}


async def test_get_sms_list_single_message(hass: HomeAssistant) -> None:
    """Test get_sms_list handles single message (dict instead of list)."""
    entry, client = await _setup_integration(hass)

    client.sms.get_sms_list.reset_mock()
    client.sms.get_sms_list.return_value = {
        "Count": "1",
        "Messages": {
            "Message": {
                "Smstat": "0",
                "Index": "40001",
                "Phone": "+1234567890",
                "Content": "Single message",
                "Date": "2026-03-29 10:00:00",
            }
        },
    }

    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_SMS_LIST,
        {ATTR_CONFIG_ENTRY_ID: entry.entry_id},
        blocking=True,
        return_response=True,
    )
    assert len(result["messages"]) == 1
    assert result["messages"][0]["content"] == "Single message"


async def test_get_sms_list_api_error(hass: HomeAssistant) -> None:
    """Test get_sms_list raises HomeAssistantError on API error."""
    entry, client = await _setup_integration(hass)

    client.sms.get_sms_list.reset_mock()
    client.sms.get_sms_list.side_effect = ResponseErrorException("API error", code=100)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_SMS_LIST,
            {ATTR_CONFIG_ENTRY_ID: entry.entry_id},
            blocking=True,
            return_response=True,
        )


async def test_delete_sms_api_error(hass: HomeAssistant) -> None:
    """Test delete_sms raises HomeAssistantError on API failure."""
    entry, client = await _setup_integration(hass)

    client.sms.delete_sms.side_effect = ResponseErrorException("API error", code=100)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DELETE_SMS,
            {ATTR_CONFIG_ENTRY_ID: entry.entry_id, "index": 40001},
            blocking=True,
        )
    client.sms.delete_sms.assert_called_once_with(40001)


async def test_mark_sms_read_api_error(hass: HomeAssistant) -> None:
    """Test mark_sms_read raises HomeAssistantError on API failure."""
    entry, client = await _setup_integration(hass)

    client.sms.set_read.side_effect = ResponseErrorException("API error", code=100)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_MARK_SMS_READ,
            {ATTR_CONFIG_ENTRY_ID: entry.entry_id, "index": 40001},
            blocking=True,
        )
    client.sms.set_read.assert_called_once_with(40001)
