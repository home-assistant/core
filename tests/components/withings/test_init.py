"""Tests for the Withings component."""
from unittest.mock import ANY

from asynctest import patch
import voluptuous as vol

import homeassistant.components.api as api
import homeassistant.components.http as http
from homeassistant.components.withings import (
    async_setup,
    const,
    CONFIG_SCHEMA,
)
from homeassistant.components.withings.config_flow import DATA_FLOW_IMPL
from homeassistant.components.withings.sensor import (
    WITHINGS_MEASUREMENTS_MAP,
)
from homeassistant.setup import async_setup_component


BASE_HASS_CONFIG = {
    http.DOMAIN: {},
    api.DOMAIN: {
        'base_url': 'http://localhost/'
    },
    const.DOMAIN: None,
}


def config_schema_validate(withings_config):
    """Assert a schema config succeeds."""
    hass_config = BASE_HASS_CONFIG.copy()
    hass_config[const.DOMAIN] = withings_config

    return CONFIG_SCHEMA(hass_config)


def config_schema_assert_fail(withings_config):
    """Assert a schema config will fail."""
    try:
        config_schema_validate(withings_config)
        assert False, "This line should not have run."
    except vol.error.MultipleInvalid:
        assert True


def test_config_schema_basic_config():
    """Test schema."""
    config_schema_validate({
        const.CLIENT_ID: 'my_client_id',
        const.CLIENT_SECRET: 'my_client_secret',
        const.PROFILES: [
            'Person 1',
            'Person 2',
        ],
    })


def test_config_schema_client_id():
    """Test schema."""
    config_schema_assert_fail({
        const.CLIENT_SECRET: 'my_client_secret',
        const.PROFILES: [
            'Person 1',
            'Person 2',
        ],
    })
    config_schema_assert_fail({
        const.CLIENT_SECRET: 'my_client_secret',
        const.CLIENT_ID: '',
        const.PROFILES: [
            'Person 1',
        ],
    })
    config_schema_validate({
        const.CLIENT_SECRET: 'my_client_secret',
        const.CLIENT_ID: 'my_client_id',
        const.PROFILES: [
            'Person 1',
        ],
    })


def test_config_schema_client_secret():
    """Test schema."""
    config_schema_assert_fail({
        const.CLIENT_ID: 'my_client_id',
        const.PROFILES: [
            'Person 1',
        ],
    })
    config_schema_assert_fail({
        const.CLIENT_ID: 'my_client_id',
        const.CLIENT_SECRET: '',
        const.PROFILES: [
            'Person 1',
        ],
    })
    config_schema_validate({
        const.CLIENT_ID: 'my_client_id',
        const.CLIENT_SECRET: 'my_client_secret',
        const.PROFILES: [
            'Person 1',
        ],
    })


def test_config_schema_profiles():
    """Test schema."""
    config_schema_assert_fail({
        const.CLIENT_ID: 'my_client_id',
        const.CLIENT_SECRET: 'my_client_secret',
    })
    config_schema_assert_fail({
        const.CLIENT_ID: 'my_client_id',
        const.CLIENT_SECRET: 'my_client_secret',
        const.PROFILES: ''
    })
    config_schema_assert_fail({
        const.CLIENT_ID: 'my_client_id',
        const.CLIENT_SECRET: 'my_client_secret',
        const.PROFILES: []
    })
    config_schema_assert_fail({
        const.CLIENT_ID: 'my_client_id',
        const.CLIENT_SECRET: 'my_client_secret',
        const.PROFILES: [
            'Person 1',
            'Person 1',
        ]
    })
    config_schema_validate({
        const.CLIENT_ID: 'my_client_id',
        const.CLIENT_SECRET: 'my_client_secret',
        const.PROFILES: [
            'Person 1',
        ]
    })
    config_schema_validate({
        const.CLIENT_ID: 'my_client_id',
        const.CLIENT_SECRET: 'my_client_secret',
        const.PROFILES: [
            'Person 1',
            'Person 2',
        ]
    })


def test_config_schema_base_url():
    """Test schema."""
    config_schema_validate({
        const.CLIENT_ID: 'my_client_id',
        const.CLIENT_SECRET: 'my_client_secret',
        const.PROFILES: [
            'Person 1',
        ]
    })
    config_schema_assert_fail({
        const.CLIENT_ID: 'my_client_id',
        const.CLIENT_SECRET: 'my_client_secret',
        const.BASE_URL: 123,
        const.PROFILES: [
            'Person 1',
        ]
    })
    config_schema_assert_fail({
        const.CLIENT_ID: 'my_client_id',
        const.CLIENT_SECRET: 'my_client_secret',
        const.BASE_URL: '',
        const.PROFILES: [
            'Person 1',
        ]
    })
    config_schema_assert_fail({
        const.CLIENT_ID: 'my_client_id',
        const.CLIENT_SECRET: 'my_client_secret',
        const.BASE_URL: 'blah blah',
        const.PROFILES: [
            'Person 1',
        ]
    })
    config_schema_validate({
        const.CLIENT_ID: 'my_client_id',
        const.CLIENT_SECRET: 'my_client_secret',
        const.BASE_URL: 'https://www.blah.blah.blah/blah/blah',
        const.PROFILES: [
            'Person 1',
        ]
    })


def test_config_schema_measurements():
    """Test schema."""
    result = config_schema_validate({
        const.CLIENT_ID: 'my_client_id',
        const.CLIENT_SECRET: 'my_client_secret',
        const.PROFILES: [
            'Person 1',
        ]
    })
    assert result[const.DOMAIN].get(const.MEASURES) == list(
        WITHINGS_MEASUREMENTS_MAP.keys()
    )

    config_schema_assert_fail({
        const.CLIENT_ID: 'my_client_id',
        const.CLIENT_SECRET: 'my_client_secret',
        const.PROFILES: [
            'Person 1',
        ],
        const.MEASURES: 123
    })
    config_schema_assert_fail({
        const.CLIENT_ID: 'my_client_id',
        const.CLIENT_SECRET: 'my_client_secret',
        const.PROFILES: [
            'Person 1',
        ],
        const.MEASURES: ''
    })
    config_schema_assert_fail({
        const.CLIENT_ID: 'my_client_id',
        const.CLIENT_SECRET: 'my_client_secret',
        const.PROFILES: [
            'Person 1',
        ],
        const.MEASURES: 'AAA'
    })
    config_schema_assert_fail({
        const.CLIENT_ID: 'my_client_id',
        const.CLIENT_SECRET: 'my_client_secret',
        const.PROFILES: [
            'Person 1',
        ],
        const.MEASURES: []
    })
    config_schema_assert_fail({
        const.CLIENT_ID: 'my_client_id',
        const.CLIENT_SECRET: 'my_client_secret',
        const.PROFILES: [
            'Person 1',
        ],
        const.MEASURES: [
            123,
        ]
    })
    config_schema_assert_fail({
        const.CLIENT_ID: 'my_client_id',
        const.CLIENT_SECRET: 'my_client_secret',
        const.PROFILES: [
            'Person 1',
        ],
        const.MEASURES: [
            'aaaa',
        ]
    })
    config_schema_assert_fail({
        const.CLIENT_ID: 'my_client_id',
        const.CLIENT_SECRET: 'my_client_secret',
        const.PROFILES: [
            'Person 1',
        ],
        const.MEASURES: [
            const.MEAS_BODY_TEMP_C,
            'AAA'
        ]
    })
    config_schema_assert_fail({
        const.CLIENT_ID: 'my_client_id',
        const.CLIENT_SECRET: 'my_client_secret',
        const.PROFILES: [
            'Person 1',
        ],
        const.MEASURES: [
            const.MEAS_BODY_TEMP_C,
            const.MEAS_BODY_TEMP_C,
        ]
    })
    result = config_schema_validate({
        const.CLIENT_ID: 'my_client_id',
        const.CLIENT_SECRET: 'my_client_secret',
        const.PROFILES: [
            'Person 1',
        ],
        const.MEASURES: [
            const.MEAS_BODY_TEMP_C,
        ]
    })
    assert result[const.DOMAIN].get(const.MEASURES) == [
        const.MEAS_BODY_TEMP_C,
    ]

    result = config_schema_validate({
        const.CLIENT_ID: 'my_client_id',
        const.CLIENT_SECRET: 'my_client_secret',
        const.PROFILES: [
            'Person 1',
        ],
        const.MEASURES: [
            const.MEAS_BODY_TEMP_C,
            const.MEAS_BODY_TEMP_F,
            const.MEAS_BONE_MASS_KG,
        ]
    })
    assert result[const.DOMAIN].get(const.MEASURES) == [
        const.MEAS_BODY_TEMP_C,
        const.MEAS_BODY_TEMP_F,
        const.MEAS_BONE_MASS_KG,
    ]


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
            const.MEASURES: [
                const.MEAS_BODY_TEMP_F,
                const.MEAS_BODY_TEMP_C
            ]
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
        async_create_task.assert_called_with(ANY)
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
