"""Test cases for digital_ocean DNS update service."""
from unittest.mock import call, patch

import pytest

from homeassistant.components.digital_ocean import DOMAIN
from homeassistant.components.digital_ocean.constants import (
    ATTR_DOMAIN_NAME,
    ATTR_RECORD_NAME,
    ATTR_RECORD_TYPE,
    ATTR_RECORD_VALUE,
)
from homeassistant.core import HomeAssistant


async def test_service_call(configured_hass: HomeAssistant, patched_domain) -> None:
    """Test case for a successful DNS update call."""
    with patch("digitalocean.Record.Record.save", autospec=True) as save_record:
        await configured_hass.services.async_call(
            DOMAIN,
            "update_domain_record",
            service_data={
                ATTR_DOMAIN_NAME: "example.com",
                ATTR_RECORD_NAME: "@",
                ATTR_RECORD_VALUE: "5.5.5.5",
                ATTR_RECORD_TYPE: "A",
            },
        )
        await configured_hass.async_block_till_done()

    patched_domain.assert_has_calls(
        [call(token="my-fake-access-token", name="example.com"), call().get_records()]
    )

    save_record.assert_called_once()
    saved_record = save_record.mock_calls[0].args[0]

    assert saved_record.domain == "example.com"
    assert saved_record.name == "@"
    assert saved_record.data == "5.5.5.5"
    assert saved_record.type == "A"


async def test_service_call_skipped(
    configured_hass: HomeAssistant, patched_domain
) -> None:
    """Test case to show how update calls are skipped if not required."""
    with patch("digitalocean.Record.Record.save", autospec=True) as save_record:
        await configured_hass.services.async_call(
            DOMAIN,
            "update_domain_record",
            service_data={
                ATTR_DOMAIN_NAME: "example.com",
                ATTR_RECORD_NAME: "@",
                ATTR_RECORD_VALUE: "1.1.1.1",
                ATTR_RECORD_TYPE: "A",
            },
        )
        await configured_hass.async_block_till_done()

    patched_domain.assert_has_calls(
        [call(token="my-fake-access-token", name="example.com"), call().get_records()]
    )
    save_record.assert_not_called()


@pytest.mark.parametrize("domain_name", ["homeassistant.com"])
async def test_service_call_record_not_found(
    configured_hass: HomeAssistant, patched_domain, domain_name
) -> None:
    """Test case to show service behavior if requested record is not found."""
    with patch("digitalocean.Record.Record.save", autospec=True) as save_record:
        await configured_hass.services.async_call(
            DOMAIN,
            "update_domain_record",
            service_data={
                ATTR_DOMAIN_NAME: domain_name,
                ATTR_RECORD_NAME: "@",
                ATTR_RECORD_VALUE: "1.1.1.1",
                ATTR_RECORD_TYPE: "A",
            },
        )
        await configured_hass.async_block_till_done()

    patched_domain.assert_has_calls(
        [
            call(token="my-fake-access-token", name="homeassistant.com"),
            call().get_records(),
        ]
    )
    save_record.assert_not_called()
