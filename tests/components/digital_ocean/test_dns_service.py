from unittest.mock import patch

from homeassistant.components.digital_ocean import DOMAIN
from homeassistant.components.digital_ocean.constants import (
    ATTR_DOMAIN_NAME,
    ATTR_RECORD_NAME,
    ATTR_RECORD_VALUE,
    ATTR_RECORD_TYPE,
)
from homeassistant.core import HomeAssistant


async def test_service_call(configured_hass: HomeAssistant, example_com_records) -> None:

    with patch('digitalocean.Record.Record.save', autospec=True) as save_record:
        await configured_hass.services.async_call(
            DOMAIN, 'update_domain_record', service_data={
                ATTR_DOMAIN_NAME: "example.com",
                ATTR_RECORD_NAME: "@",
                ATTR_RECORD_VALUE: "5.5.5.5",
                ATTR_RECORD_TYPE: "A"
            }
        )
        await configured_hass.async_block_till_done()

    example_com_records.assert_called_once_with(
        params={'name': 'example.com', 'type': 'A'}
    )
    save_record.assert_called_once()
    saved_record = save_record.mock_calls[0].args[0]

    assert saved_record.domain == 'example.com'
    assert saved_record.name == '@'
    assert saved_record.data == '5.5.5.5'
    assert saved_record.type == 'A'


async def test_service_call_skipped(configured_hass: HomeAssistant, example_com_records) -> None:
    with patch('digitalocean.Record.Record.save', autospec=True) as save_record:
        await configured_hass.services.async_call(
            DOMAIN, 'update_domain_record', service_data={
                ATTR_DOMAIN_NAME: "example.com",
                ATTR_RECORD_NAME: "@",
                ATTR_RECORD_VALUE: "1.1.1.1",
                ATTR_RECORD_TYPE: "A"
            }
        )
        await configured_hass.async_block_till_done()

    example_com_records.assert_called_once_with(
        params={'name': 'example.com', 'type': 'A'}
    )
    save_record.assert_not_called()


async def test_service_call_record_not_found(configured_hass: HomeAssistant, example_com_records) -> None:
    example_com_records.return_value = []
    with patch('digitalocean.Record.Record.save', autospec=True) as save_record:
        await configured_hass.services.async_call(
            DOMAIN, 'update_domain_record', service_data={
                ATTR_DOMAIN_NAME: "homeassistant.com",
                ATTR_RECORD_NAME: "@",
                ATTR_RECORD_VALUE: "1.1.1.1",
                ATTR_RECORD_TYPE: "A"
            }
        )
        await configured_hass.async_block_till_done()

    example_com_records.assert_called_once_with(
        params={'name': 'homeassistant.com', 'type': 'A'}
    )
    save_record.assert_not_called()
