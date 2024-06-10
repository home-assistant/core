"""Test the zabbix integration."""

import asyncio
from datetime import timedelta
from unittest.mock import MagicMock, patch

from zabbix_utils import APIRequestError, ProcessingError

import homeassistant.components.zabbix as patched_zabbix
from homeassistant.components.zabbix.const import (
    DOMAIN,
    NEW_CONFIG,
    ZABBIX_THREAD_INSTANCE,
    ZAPI,
)
from homeassistant.const import STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .const import (
    MOCK_CONFIG_DATA_SENDER,
    MOCK_CONFIG_DATA_SENSOR_TOKEN,
    MOCK_CONFIG_DATA_SENSOR_USERPASS,
    MOCK_CONFIGURATION,
    MOCK_FAKE_ENTITY,
    MOCK_ZABBIX_API_VERSION,
)

from tests.common import MockConfigEntry


async def test_async_setup_entry_sensor_userpass_success(
    hass: HomeAssistant,
) -> None:
    """Testing integration setup via config entry for sensors with User/Password."""

    with (
        patch(
            "homeassistant.components.zabbix.ZabbixAPI",
        ) as MockZabbixAPI,
        patch.object(
            hass.config_entries, "async_forward_entry_setups"
        ) as sensors_setups_mock,
    ):
        mock_instance_api = MockZabbixAPI.return_value
        mock_instance_api.api_version = MagicMock(return_value=MOCK_ZABBIX_API_VERSION)
        mock_instance_api.login = MagicMock()
        mock_instance_api.check_auth = MagicMock()

        entry = MockConfigEntry(
            domain=DOMAIN,
            data=MOCK_CONFIG_DATA_SENSOR_USERPASS,
            title="Zabbix integration",
            entry_id="mock_entry",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert sensors_setups_mock.call_count == 1
        assert sensors_setups_mock.call_args.args[0] == entry
        assert sensors_setups_mock.call_args.args[1] == ["sensor"]


async def test_async_setup_entry_sensor_token_login_exception(
    hass: HomeAssistant,
) -> None:
    """Testing integration setup via config entry for sensors with User/Password."""

    with (
        patch(
            "homeassistant.components.zabbix.ZabbixAPI",
        ) as MockZabbixAPI,
    ):
        mock_instance_api = MockZabbixAPI.return_value
        mock_instance_api.api_version = MagicMock(return_value=MOCK_ZABBIX_API_VERSION)
        mock_instance_api.login = MagicMock()
        mock_instance_api.check_auth = MagicMock(
            side_effect=APIRequestError("login error")
        )

        entry = MockConfigEntry(
            domain=DOMAIN,
            data=MOCK_CONFIG_DATA_SENSOR_TOKEN,
            title="Zabbix integration",
            entry_id="mock_entry",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert hass.data[DOMAIN][entry.entry_id][ZAPI] is None


async def test_async_setup_entry_sensor_token_http_error(
    hass: HomeAssistant,
) -> None:
    """Testing integration setup via config entry for sensors with User/Password."""

    with (
        patch(
            "homeassistant.components.zabbix.ZabbixAPI",
        ) as MockZabbixAPI,
    ):
        mock_instance_api = MockZabbixAPI.return_value
        mock_instance_api.api_version = MagicMock(return_value=MOCK_ZABBIX_API_VERSION)
        mock_instance_api.login = MagicMock()
        mock_instance_api.check_auth = MagicMock(
            side_effect=ProcessingError("http error")
        )

        entry = MockConfigEntry(
            domain=DOMAIN,
            data=MOCK_CONFIG_DATA_SENSOR_TOKEN,
            title="Zabbix integration",
            entry_id="mock_entry",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert hass.data[DOMAIN][entry.entry_id][ZAPI] is None


async def test_async_setup_entry_sender(
    hass: HomeAssistant,
) -> None:
    """Testing integration setup via config entry for sender."""

    with (
        patch(
            "homeassistant.components.zabbix.Sender",
        ) as MockSender,
        patch("homeassistant.components.zabbix.BATCH_BUFFER_SIZE", 1),
    ):
        mock_instance_api = MockSender.return_value

        entry = MockConfigEntry(
            domain=DOMAIN,
            data=MOCK_CONFIG_DATA_SENDER,
            title="Zabbix integration",
            entry_id="mock_entry",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        # Test that zabbix thread is there
        assert hass.data[DOMAIN][entry.entry_id][ZABBIX_THREAD_INSTANCE] is not None

        # Test for entity in wrong state
        hass.states.async_set("some.entity", STATE_UNKNOWN)
        # Test for entity not in include_exclude filter
        hass.states.async_set("some.entity", "2")
        await hass.async_block_till_done()
        # Test for entity in include filter, but state raises ValueError and treated as string
        hass.states.async_set(MOCK_FAKE_ENTITY, "something")
        await hass.async_block_till_done()
        # Test for entity in include filter, but state raises ValueError but converted with state_helper.state_as_number
        # This is sent
        hass.states.async_set(MOCK_FAKE_ENTITY, STATE_ON)
        # Test if old events are dropped and not send
        with patch(
            "homeassistant.components.zabbix.RETRY_DELAY",
            -1000,
        ):
            hass.states.async_set(
                entity_id=MOCK_FAKE_ENTITY,
                new_state="10",
                timestamp=dt_util.as_timestamp(dt_util.now() - timedelta(seconds=1000)),
            )
        # Test for entity in include filter and with multiplr attributes
        # This is sent
        hass.states.async_set(
            MOCK_FAKE_ENTITY,
            "3",
            {
                "attr_1": "val",
                "attr_2": 2,
                "attr_3": 4,
            },
        )
        await hass.async_block_till_done()
        await hass.async_block_till_done()
        # Waiting for thread to do the thing
        await asyncio.sleep(1)
        # Test if Sender.send was actually called two times for STATE_ON and for "3"
        assert mock_instance_api.send.call_count == 2


async def test_async_setup_entry_sender_send_exception(
    hass: HomeAssistant,
) -> None:
    """Testing integration setup via config entry for sender."""

    with (
        patch(
            "homeassistant.components.zabbix.Sender",
        ) as MockSender,
        patch("homeassistant.components.zabbix.BATCH_BUFFER_SIZE", 1),
        patch("homeassistant.components.zabbix.RETRY_DELAY", 0),
    ):
        mock_instance_api = MockSender.return_value
        mock_instance_api.send = MagicMock(side_effect=ProcessingError("http error"))

        entry = MockConfigEntry(
            domain=DOMAIN,
            data=MOCK_CONFIG_DATA_SENDER,
            title="Zabbix integration",
            entry_id="mock_entry",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        # Test that zabbix thread is there
        assert hass.data[DOMAIN][entry.entry_id][ZABBIX_THREAD_INSTANCE] is not None

        hass.states.async_set(MOCK_FAKE_ENTITY, "30")
        await hass.async_block_till_done()
        # Waiting for thread to do the thing
        await asyncio.sleep(1)

        hass.data[DOMAIN][entry.entry_id].update({ZAPI: MagicMock().return_value})

        # send this one in order to clear write_errors
        mock_instance_api.send = MagicMock()
        hass.states.async_set(MOCK_FAKE_ENTITY, "40")
        await hass.async_block_till_done()
        await hass.async_block_till_done()
        # Waiting for thread work
        await asyncio.sleep(1)
        # Test if Sender.send was actually called two times for for "40"
        assert mock_instance_api.send.call_count == 1


async def test_async_setup_entry_not_run_if_configuration_file_used(
    hass: HomeAssistant,
) -> None:
    """Testing integration setup via config entry is not run if configuration.yaml file used for zabbix."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_DATA_SENDER,
        title="Zabbix integration",
        entry_id="mock_entry",
    )
    entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {NEW_CONFIG: False})
    with patch("homeassistant.components.zabbix.async_setup", return_value=True):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    # Test that no zabbix thread related data created
    assert hass.data[DOMAIN].get(entry.entry_id) is None


async def test_async_setup_zabbix_login_error(
    hass: HomeAssistant,
) -> None:
    """Testing integration setup via configuration.yaml ."""

    config = MOCK_CONFIGURATION
    with (
        patch("homeassistant.components.zabbix.ZabbixAPI") as MockZabbixAPI,
        patch("homeassistant.components.zabbix.Sender"),
        patch.object(
            patched_zabbix,
            "async_start_retry",
            wraps=patched_zabbix.async_start_retry,
            spec=patched_zabbix.async_start_retry,
        ) as mock_async_start_retry,
    ):
        mock_zabbix_api = MockZabbixAPI.return_value
        # Test unable to login
        mock_zabbix_api.check_auth = MagicMock(
            side_effect=APIRequestError("login error")
        )
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        assert mock_async_start_retry.call_count == 1
        # But still we should have zabbix sender thread started
        assert hass.data[DOMAIN].get(ZABBIX_THREAD_INSTANCE) is not None


async def test_async_setup_zabbix_http_error(
    hass: HomeAssistant,
) -> None:
    """Testing integration setup via configuration.yaml ."""

    config = MOCK_CONFIGURATION
    with (
        patch("homeassistant.components.zabbix.ZabbixAPI") as MockZabbixAPI,
        patch("homeassistant.components.zabbix.Sender"),
        patch.object(
            patched_zabbix,
            "async_start_retry",
            wraps=patched_zabbix.async_start_retry,
            spec=patched_zabbix.async_start_retry,
        ) as mock_async_start_retry,
    ):
        mock_zabbix_api = MockZabbixAPI.return_value

        # Test unable to connect
        mock_zabbix_api.check_auth = MagicMock(
            side_effect=ProcessingError("http error")
        )
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        assert mock_async_start_retry.call_count == 1
        # But still we should have zabbix sender thread started
        assert hass.data[DOMAIN].get(ZABBIX_THREAD_INSTANCE) is not None


async def test_async_setup_all_success(
    hass: HomeAssistant,
) -> None:
    """Testing integration setup via configuration.yaml ."""

    config = MOCK_CONFIGURATION
    with (
        patch("homeassistant.components.zabbix.ZabbixAPI"),
        patch("homeassistant.components.zabbix.Sender"),
        patch.object(
            patched_zabbix,
            "async_start_retry",
            wraps=patched_zabbix.async_start_retry,
            spec=patched_zabbix.async_start_retry,
        ) as mock_async_start_retry,
    ):
        # mock_zabbix_api = MockZabbixAPI.return_value

        # Test able to connect, and set zapi as not None
        await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        assert mock_async_start_retry.call_count == 0
        assert hass.data[DOMAIN].get(ZAPI, None) is not None
