"""Tests for the Withings component."""
from asynctest import patch
from homeassistant.setup import async_setup_component
import homeassistant.components.http as http
import homeassistant.components.api as api
from homeassistant.components.withings import (
    async_setup,
    const,
)
from homeassistant.components.withings.config_flow import DATA_FLOW_IMPL


async def test_async_setup(hass):
    """Test method."""
    config = {
        http.DOMAIN: {},
        api.DOMAIN: {
            'base_url': 'http://localhost/'
        },
        const.DOMAIN: {
            const.CLIENT_ID: 'my_client_id',
            const.CLIENT_SECRET: 'my_client_secret',
            const.PROFILES: [
                'Person 1',
                'Person 2',
            ],
        },
    }

    result = await async_setup_component(hass, 'http', config)
    assert result

    result = await async_setup_component(hass, 'api', config)
    assert result

    async_create_task_patch = patch.object(
        hass,
        'async_create_task',
        wraps=hass.async_create_task
    )
    async_init_patch = patch.object(
        hass.config_entries.flow,
        'async_init',
        wraps=hass.config_entries.flow.async_init
    )

    with async_create_task_patch as async_create_task, \
            async_init_patch as async_init:
        result = await async_setup(hass, config)
        assert result is True
        async_create_task.assert_called()
        async_init.assert_called_with(
            const.DOMAIN,
            context={'source': const.SOURCE_USER},
            data={}
        )

        assert hass.data[DATA_FLOW_IMPL]['Person 1'] == {
            const.CLIENT_ID: 'my_client_id',
            const.CLIENT_SECRET: 'my_client_secret',
            const.BASE_URL: 'http://127.0.0.1:8123',
            const.PROFILE: 'Person 1',
        }
        assert hass.data[DATA_FLOW_IMPL]['Person 2'] == {
            const.CLIENT_ID: 'my_client_id',
            const.CLIENT_SECRET: 'my_client_secret',
            const.BASE_URL: 'http://127.0.0.1:8123',
            const.PROFILE: 'Person 2',
        }
