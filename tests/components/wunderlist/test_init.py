"""Test the Dyson fan component."""
import logging
from unittest.mock import patch

from homeassistant.setup import async_setup_component
from homeassistant.components import wunderlist
from homeassistant.const import (
    CONF_TYPE)

_LOGGER = logging.getLogger(__name__)

mock_lists = [
    {
        "id": 83526310,
        "title": "Test list",
        "revision": 10
    }
]

mock_tasks = [
    {
        "id": 409233670,
        "list_id": 83526310,
        "revision": 1,
        "starred": True,
        "title": "Task1",
    },
    {
        "id": 123892713,
        "list_id": 83526310,
        "revision": 1,
        "starred": True,
        "title": "Task2",
    }
]

mock_task_positions = [
    {
        "id": 83526310,
        "values": [123892713, 409233670],
        "revision": 1,
        "type": "list_position"
    }
]


async def test_successful_login(hass):
    """Testing a successful creation of an instance."""
    with patch('wunderpy2.wunderclient.lists_endpoint.get_lists',
               return_value=mock_lists) as mock_get_lists:
        assert await async_setup_component(hass, wunderlist.DOMAIN, {
            wunderlist.DOMAIN: {
                wunderlist.CONF_CLIENT_ID: "abc123",
                wunderlist.CONF_ACCESS_TOKEN: "def456",
            }
        })

        assert wunderlist.DOMAIN in hass.config.components
        assert mock_get_lists.called


async def test_failed_login(hass):
    """Component creation should fail in case of login error."""
    with patch('wunderpy2.wunderclient.lists_endpoint.get_lists',
               side_effect=Exception('Test')) as mock_get_lists:
        assert await async_setup_component(hass, wunderlist.DOMAIN, {
            wunderlist.DOMAIN: {
                wunderlist.CONF_CLIENT_ID: "abc123",
                wunderlist.CONF_ACCESS_TOKEN: "def456",
            }
        }) is False

        assert wunderlist.DOMAIN not in hass.config.components
        assert mock_get_lists.called


async def test_list_tasks(hass, hass_ws_client):
    """Test async added to hass."""
    with patch('wunderpy2.wunderclient.lists_endpoint.get_lists',
               return_value=mock_lists) as mock_get_lists, \
            patch('wunderpy2.wunderclient.positions_endpoints.get_task_positions_objs',
                  return_value=mock_task_positions) as mock_get_task_positions, \
            patch('wunderpy2.wunderclient.tasks_endpoint.get_tasks',
                  return_value=mock_tasks) as mock_get_tasks:
        assert await async_setup_component(hass, wunderlist.DOMAIN, {
            wunderlist.DOMAIN: {
                wunderlist.CONF_CLIENT_ID: "abc123",
                wunderlist.CONF_ACCESS_TOKEN: "def456",
            }
        })

        ws_client = await hass_ws_client(hass)

        await ws_client.send_json({
            'id': 5,
            CONF_TYPE: wunderlist.WS_TYPE_LIST_TASKS,
            wunderlist.CONF_LIST_ID: '83526310',
        })
        msg = await ws_client.receive_json()


        assert len(msg['result']) == 2
        assert msg['result'][0]['id'] == 123892713
        assert msg['result'][1]['id'] == 409233670

        assert mock_get_lists.called
        assert mock_get_task_positions.called
        assert mock_get_tasks.called
