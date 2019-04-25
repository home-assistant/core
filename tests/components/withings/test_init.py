"""Tests for the Withings component."""
from asynctest import patch
import voluptuous as vol
from homeassistant.setup import async_setup_component
import homeassistant.components.http as http
import homeassistant.components.api as api
from homeassistant.components.withings import (
    async_setup,
    const,
    CONFIG_SCHEMA
)
from homeassistant.components.withings.config_flow import DATA_FLOW_IMPL
from homeassistant.components.withings.sensor import (
    WITHINGS_MEASUREMENTS_MAP
)


class TestConfigSchema:
    """Test the config schema."""

    def validate(self, config):
        """Assert a schema config succeeds."""
        return CONFIG_SCHEMA({
            http.DOMAIN: {},
            api.DOMAIN: {
                'base_url': 'http://localhost/'
            },
            const.DOMAIN: config
        })

    def assert_fail(self, config):
        """Assert a schema config will fail."""
        try:
            self.validate(config)
            assert False, "This line should not have run."
        except vol.error.MultipleInvalid:
            assert True

    def test_basic_config(self):
        """Test schema."""
        self.validate({
            const.CLIENT_ID: 'my_client_id',
            const.CLIENT_SECRET: 'my_client_secret',
            const.PROFILES: [
                'Person 1',
                'Person 2',
            ],
        })

    def test_client_id(self):
        """Test schema."""
        self.assert_fail({
            const.CLIENT_SECRET: 'my_client_secret',
            const.PROFILES: [
                'Person 1',
                'Person 2',
            ],
        })
        self.assert_fail({
            const.CLIENT_SECRET: 'my_client_secret',
            const.CLIENT_ID: '',
            const.PROFILES: [
                'Person 1',
            ],
        })
        self.validate({
            const.CLIENT_SECRET: 'my_client_secret',
            const.CLIENT_ID: 'my_client_id',
            const.PROFILES: [
                'Person 1',
            ],
        })

    def test_client_secret(self):
        """Test schema."""
        self.assert_fail({
            const.CLIENT_ID: 'my_client_id',
            const.PROFILES: [
                'Person 1',
            ],
        })
        self.assert_fail({
            const.CLIENT_ID: 'my_client_id',
            const.CLIENT_SECRET: '',
            const.PROFILES: [
                'Person 1',
            ],
        })
        self.validate({
            const.CLIENT_ID: 'my_client_id',
            const.CLIENT_SECRET: 'my_client_secret',
            const.PROFILES: [
                'Person 1',
            ],
        })

    def test_profiles(self):
        """Test schema."""
        self.assert_fail({
            const.CLIENT_ID: 'my_client_id',
            const.CLIENT_SECRET: 'my_client_secret',
        })
        self.assert_fail({
            const.CLIENT_ID: 'my_client_id',
            const.CLIENT_SECRET: 'my_client_secret',
            const.PROFILES: ''
        })
        self.assert_fail({
            const.CLIENT_ID: 'my_client_id',
            const.CLIENT_SECRET: 'my_client_secret',
            const.PROFILES: []
        })
        self.assert_fail({
            const.CLIENT_ID: 'my_client_id',
            const.CLIENT_SECRET: 'my_client_secret',
            const.PROFILES: [
                'Person 1',
                'Person 1',
            ]
        })
        self.validate({
            const.CLIENT_ID: 'my_client_id',
            const.CLIENT_SECRET: 'my_client_secret',
            const.PROFILES: [
                'Person 1',
            ]
        })
        self.validate({
            const.CLIENT_ID: 'my_client_id',
            const.CLIENT_SECRET: 'my_client_secret',
            const.PROFILES: [
                'Person 1',
                'Person 2',
            ]
        })

    def test_base_url(self):
        """Test schema."""
        self.validate({
            const.CLIENT_ID: 'my_client_id',
            const.CLIENT_SECRET: 'my_client_secret',
            const.PROFILES: [
                'Person 1',
            ]
        })
        self.assert_fail({
            const.CLIENT_ID: 'my_client_id',
            const.CLIENT_SECRET: 'my_client_secret',
            const.BASE_URL: 123,
            const.PROFILES: [
                'Person 1',
            ]
        })
        self.assert_fail({
            const.CLIENT_ID: 'my_client_id',
            const.CLIENT_SECRET: 'my_client_secret',
            const.BASE_URL: '',
            const.PROFILES: [
                'Person 1',
            ]
        })
        self.assert_fail({
            const.CLIENT_ID: 'my_client_id',
            const.CLIENT_SECRET: 'my_client_secret',
            const.BASE_URL: 'blah blah',
            const.PROFILES: [
                'Person 1',
            ]
        })
        self.validate({
            const.CLIENT_ID: 'my_client_id',
            const.CLIENT_SECRET: 'my_client_secret',
            const.BASE_URL: 'https://www.blah.blah.blah/blah/blah',
            const.PROFILES: [
                'Person 1',
            ]
        })

    def test_measurements(self):
        """Test schema."""
        result = self.validate({
            const.CLIENT_ID: 'my_client_id',
            const.CLIENT_SECRET: 'my_client_secret',
            const.PROFILES: [
                'Person 1',
            ]
        })
        assert result[const.DOMAIN].get(const.MEASURES) == list(
            WITHINGS_MEASUREMENTS_MAP.keys()
        )

        self.assert_fail({
            const.CLIENT_ID: 'my_client_id',
            const.CLIENT_SECRET: 'my_client_secret',
            const.PROFILES: [
                'Person 1',
            ],
            const.MEASURES: 123
        })
        self.assert_fail({
            const.CLIENT_ID: 'my_client_id',
            const.CLIENT_SECRET: 'my_client_secret',
            const.PROFILES: [
                'Person 1',
            ],
            const.MEASURES: ''
        })
        self.assert_fail({
            const.CLIENT_ID: 'my_client_id',
            const.CLIENT_SECRET: 'my_client_secret',
            const.PROFILES: [
                'Person 1',
            ],
            const.MEASURES: 'AAA'
        })
        self.assert_fail({
            const.CLIENT_ID: 'my_client_id',
            const.CLIENT_SECRET: 'my_client_secret',
            const.PROFILES: [
                'Person 1',
            ],
            const.MEASURES: []
        })
        self.assert_fail({
            const.CLIENT_ID: 'my_client_id',
            const.CLIENT_SECRET: 'my_client_secret',
            const.PROFILES: [
                'Person 1',
            ],
            const.MEASURES: [
                123,
            ]
        })
        self.assert_fail({
            const.CLIENT_ID: 'my_client_id',
            const.CLIENT_SECRET: 'my_client_secret',
            const.PROFILES: [
                'Person 1',
            ],
            const.MEASURES: [
                'aaaa',
            ]
        })
        self.assert_fail({
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
        self.assert_fail({
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
        result = self.validate({
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

        result = self.validate({
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
