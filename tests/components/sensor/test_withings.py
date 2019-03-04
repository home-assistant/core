"""Tests for the Withings sensor platform."""
import asyncio
import unittest
import os
import time
import datetime
import nokia
import callee
from asynctest import patch, MagicMock
from aiohttp.web_request import BaseRequest
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (CONF_PLATFORM)
from homeassistant.setup import async_setup_component
import homeassistant.components.http as http
import homeassistant.components.api as api
import homeassistant.components.configurator as configurator
import homeassistant.components.sensor.withings as withings
from tests.common import get_test_home_assistant


PLATFORM_NAME = 'withings'


def async_test(coro):
    """Allow unittest methods to be async."""
    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(coro(*args, **kwargs))
    return wrapper


async def test_async_setup_platform(hass):
    """Test method."""
    profile = 'person 1'
    slug = 'person_1'

    config = {
        http.DOMAIN: {},
        api.DOMAIN: {
            'base_url': 'http://localhost/'
        },
        SENSOR_DOMAIN: [
            {
                CONF_PLATFORM: PLATFORM_NAME,
                withings.CONF_CLIENT_ID: 'my_client_id',
                withings.CONF_SECRET: 'my_secret',
                withings.CONF_PROFILE: profile
            }
        ]
    }

    credentials_file_path = hass.config.path(
        withings.WITHINGS_CONFIG_FILE.format(
            'my_client_id',
            slug
        )
    )

    if os.path.isfile(credentials_file_path):
        os.remove(credentials_file_path)

    result = await async_setup_component(hass, 'http', config)
    assert result

    result = await async_setup_component(hass, 'api', config)
    assert result

    with \
            patch.object(
                    hass.http, 'register_view',
                    wraps=hass.http.register_view
            ) as register_view_spy,\
            patch(
                'homeassistant.components.configurator.async_request_config',
                wraps=configurator.async_request_config
            ) as async_request_config_spy, \
            patch(
                'homeassistant.components.configurator.async_request_done',
                wraps=configurator.async_request_done
            ) as async_request_done_spy, \
            patch(
                'homeassistant.components.sensor.withings.async_initialize'
            ) as async_initialize_mock:

        # Simulate an initial setup.
        result = await async_setup_component(hass, SENSOR_DOMAIN, config)
        assert result
        assert withings.DATA_CONFIGURING in hass.data
        assert 'person_1' in hass.data[withings.DATA_CONFIGURING]
        configuring = hass.data[withings.DATA_CONFIGURING][slug]
        assert isinstance(configuring, withings.WithingsConfiguring)
        assert callable(configuring.oauth_initialize_callback)
        register_view_spy.assert_called_with(
            withings.WithingsAuthCallbackView(
                slug,
                '%s/%s' % (
                    withings.WITHINGS_AUTH_CALLBACK_PATH,
                    slug
                )
            )
        )
        async_request_config_spy.assert_called_with(
            hass,
            'Withings',
            # pylint: disable=line-too-long
            description="Authorization is required to get access to Withings data. After clicking the button below, be sure to choose the profile that maps to '%s'." % profile,  # noqa: E501
            link_name="Click here to authorize Home Assistant.",
            # pylint: disable=line-too-long
            link_url=callee.StartsWith('https://account.withings.com/oauth2_user/authorize2?response_type=code&client_id=my_client_id&redirect_uri=http%3A%2F%2F127.0.0.1%3A8123%2Fapi%2Fwithings%2Fcallback%2Fperson_1&scope=user.info%2Cuser.metrics%2Cuser.activity&state=')  # noqa: E501
        )

        # Get the instance of WithingsAuthCallbackView used when registering.
        args = register_view_spy.call_args_list
        callback_view = args[0][0][0]

        get_credentials_mock = patch.object(
            configuring.auth_client,
            'get_credentials',
            return_value=nokia.NokiaCredentials
        )
        get_credentials_mock.start()

        # Simulate a request to the callback view.
        request = MagicMock(spec=BaseRequest)
        request.app = {
            'hass': hass
        }
        request.query = {
            'state': 'my_state',
            'code': 'my_code'
        }

        callback_view.get(request)
        await hass.async_block_till_done()

        configuring.auth_client.get_credentials.assert_called_with('my_code')
        async_initialize_mock.assert_called()
        async_request_done_spy.assert_called()


async def test_async_setup_platform_from_saved_credentials(hass):
    """Test method."""
    profile = 'person 1'
    slug = 'person_1'

    config = {
        http.DOMAIN: {},
        api.DOMAIN: {
            'base_url': 'http://localhost/'
        },
        SENSOR_DOMAIN: [
            {
                CONF_PLATFORM: PLATFORM_NAME,
                withings.CONF_CLIENT_ID: 'my_client_id',
                withings.CONF_SECRET: 'my_secret',
                withings.CONF_PROFILE: profile
            }
        ]
    }

    withings.write_credentials_to_file(
        hass,
        withings.WITHINGS_CONFIG_FILE.format(
            'my_client_id',
            slug
        ),
        nokia.NokiaCredentials()
    )

    with patch(
            'homeassistant.components.sensor.withings.async_initialize'
    ) as async_initialize_mock:
        result = await async_setup_component(hass, 'http', config)
        assert result

        result = await async_setup_component(hass, 'api', config)
        assert result

        result = await async_setup_component(hass, SENSOR_DOMAIN, config)
        assert result

        async_initialize_mock.assert_called()


async def test_initialize_new_credentials(hass):
    """Test method."""
    profile = 'person 1'
    slug = 'person_1'

    config = {
        CONF_PLATFORM: PLATFORM_NAME,
        withings.CONF_CLIENT_ID: 'my_client_id',
        withings.CONF_SECRET: 'my_secret',
        withings.CONF_PROFILE: profile,
        withings.CONF_MEASUREMENTS: list(withings.CONF_SENSORS.keys())
    }

    add_entities_mock = MagicMock()

    configuring = withings.WithingsConfiguring(
        hass,
        config,
        add_entities_mock,
        slug,
        '/tmp/testfile',
        None,
        None,
    )

    creds = nokia.NokiaCredentials(
        None,
        9999999999
    )

    await withings.async_initialize(configuring, creds)

    sensors = add_entities_mock.call_args_list[0][0][0]
    measurements = []
    for sensor in sensors:
        measurements.append(sensor.attribute.measurement)

    assert set(measurements) == set(withings.WITHINGS_MEASUREMENTS_MAP.keys())


async def test_initialize_credentials_refreshed(hass):
    """Test method."""
    profile = 'person 1'
    slug = 'person_1'

    config = {
        CONF_PLATFORM: PLATFORM_NAME,
        withings.CONF_CLIENT_ID: 'my_client_id',
        withings.CONF_SECRET: 'my_secret',
        withings.CONF_PROFILE: profile,
        withings.CONF_MEASUREMENTS: list(withings.CONF_SENSORS.keys())
    }

    add_entities_mock = MagicMock()

    configuring = withings.WithingsConfiguring(
        hass,
        config,
        add_entities_mock,
        slug,
        '/tmp/testfile',
        None,
        None,
    )

    creds = nokia.NokiaCredentials(
        None,
        9999999999
    )

    data_manager = await withings.async_initialize(configuring, creds)

    with patch(
            'homeassistant.components.sensor.withings.credentials_refreshed',
            wraps=withings.credentials_refreshed
    ) as credentials_refreshed_spy:
        data_manager.get_api().set_token({
            'expires_in': 22222,
            'access_token': 'ACCESS_TOKEN',
            'refresh_token': 'REFRESH_TOKEN'
        })

        credentials_refreshed_spy.assert_called()


class TestWithingsAuthCallbackView(unittest.TestCase):
    """Tests the auth callback view."""

    def setUp(self):
        """Set up the test."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Tear down the test."""
        self.hass.stop()

    @staticmethod
    def test_init():
        """Test method."""
        view = withings.WithingsAuthCallbackView('person_1', 'url1')
        assert view.slug == 'person_1'
        assert view.url == 'url1'
        assert not view.requires_auth
        assert view.name == 'api:withings:callback:person_1'

    def test_get_errors(self):
        """Test method."""
        request = MagicMock(spec=BaseRequest)
        request.app = {
            'hass': self.hass
        }
        request.query = {
            'state': 'my_state',
            'code': 'my_code'
        }

        view = withings.WithingsAuthCallbackView('person_1', 'url1')

        request.query = {}
        response = view.get(request)
        assert response.body.startswith(b'ERROR_0002:')

        request.query = {'error': 'MY_ERROR'}
        response = view.get(request)
        assert response.body.startswith(b'ERROR_0001:')

        request.query = {'state': 'MY_STATE'}
        response = view.get(request)
        assert response.body.startswith(b'ERROR_0002:')

        request.query = {'code': 'MY_CODE'}
        response = view.get(request)
        assert response.body.startswith(b'ERROR_0002:')

        request.query = {'state': 'MY_STATE', 'code': 'MY_CODE'}
        response = view.get(request)
        assert response.body.startswith(b'ERROR_0003:')

        request.query = {'state': 'MY_STATE', 'code': 'MY_CODE'}
        self.hass.data[withings.DATA_CONFIGURING] = {}
        response = view.get(request)
        assert response.body.startswith(b'ERROR_0004:')

    @staticmethod
    def test___eq__():
        """Test method."""
        view1a = withings.WithingsAuthCallbackView('profile_1', 'url1')
        view1b = withings.WithingsAuthCallbackView('profile_1', 'url1')
        view2a = withings.WithingsAuthCallbackView('profile_2', 'url1')

        assert view1a == view1b
        assert view1a != view2a
        assert view1b != view2a
        assert view1a != {}
        assert view1a != 'HELLO'


class TestWithingsDataManager(unittest.TestCase):
    """Tests the data manager class."""

    def setUp(self):
        """Set up the test."""
        self.hass = get_test_home_assistant()
        self.api = nokia.NokiaApi.__new__(nokia.NokiaApi)
        self.api.get_measures = MagicMock()
        self.api.get_sleep = MagicMock()

    def tearDown(self):
        """Tear down the test."""
        self.hass.stop()

    @async_test
    async def test_async_update_measures(self):
        """Test method."""
        data_manager = withings.WithingsDataManager(
            'person_1',
            self.api
        )

        self.api.get_measures = MagicMock(return_value='DATA')
        results1 = await data_manager.async_update_measures()
        self.api.get_measures.assert_called()
        assert results1 == 'DATA'

        self.api.get_measures.reset_mock()

        self.api.get_measures = MagicMock(return_value='DATA_NEW')
        await data_manager.async_update_measures()
        self.api.get_measures.assert_not_called()

    @async_test
    async def test_async_update_sleep(self):
        """Test method."""
        data_manager = withings.WithingsDataManager(
            'person_1',
            self.api
        )

        with patch('time.time', return_value=100000.101):
            self.api.get_sleep = MagicMock(return_value='DATA')
            results1 = await data_manager.async_update_sleep()
            self.api.get_sleep.assert_called_with(
                startdate=78400,
                enddate=100000
            )
            assert results1 == 'DATA'

            self.api.get_sleep.reset_mock()

            self.api.get_sleep = MagicMock(return_value='DATA_NEW')
            await data_manager.async_update_sleep()
            self.api.get_sleep.assert_not_called()

    @async_test
    async def test_async_update_sleep_summary(self):
        """Test method."""
        now = datetime.datetime.utcnow()
        noon = datetime.datetime(
            now.year, now.month, now.day,
            12, 0, 0, 0,
            datetime.timezone.utc
        )
        yesterday_noon_timestamp = noon.timestamp() - 86400

        data_manager = withings.WithingsDataManager(
            'person_1',
            self.api
        )

        self.api.get_sleep_summary = MagicMock(return_value='DATA')
        results1 = await data_manager.async_update_sleep_summary()
        self.api.get_sleep_summary.assert_called_with(
            lastupdate=callee.And(
                callee.GreaterOrEqualTo(yesterday_noon_timestamp),
                callee.LessThan(yesterday_noon_timestamp + 10)
            )
        )
        assert results1 == 'DATA'

        self.api.get_sleep_summary.reset_mock()

        self.api.get_sleep_summary = MagicMock(return_value='DATA_NEW')
        await data_manager.async_update_sleep_summary()
        self.api.get_sleep_summary.assert_not_called()


class TestWithingsHealthSensor(unittest.TestCase):
    """Tests all the health sensors."""

    def setUp(self):
        """Set up the test."""
        self.hass = get_test_home_assistant()

        self.api = nokia.NokiaApi.__new__(nokia.NokiaApi)
        self.api.get_credentials = MagicMock(
            return_value=nokia.NokiaCredentials(
                user_id='USER_ID'
            )
        )
        self.api.get_measures = MagicMock()
        self.api.get_sleep = MagicMock()
        self.api.get_sleep_summary = MagicMock()

        self.recreate_data_manager()

    def tearDown(self):
        """Tear down the test."""
        self.hass.stop()

    def recreate_data_manager(self):
        """Recreate data manager to get arround the @Trottle decorators."""
        self.data_manager = withings.WithingsDataManager(
            'person_1',
            self.api
        )

    def test_properties(self):
        """Test method."""
        sensor = withings.WithingsHealthSensor(
            self.data_manager,
            withings.WITHINGS_MEASUREMENTS_MAP[withings.MEAS_WEIGHT_KG]
        )

        assert sensor.name == 'Withings weight_kg person_1'
        assert sensor.unique_id == 'withings_person_1_USER_ID_weight_kg'
        assert sensor.state is None
        assert sensor.unit_of_measurement == 'kg'
        assert sensor.icon == 'mdi:weight-kilogram'

    @async_test
    async def test_async_update(self):
        """Test method."""
        self.api.get_measures.return_value = nokia.NokiaMeasures({
            'updatetime': '',
            'timezone': '',
            'measuregrps': [
                # Un-ambiguous groups.
                new_measure_group(
                    1, 0, time.time(), time.time(), 1, 'DEV_ID', False, 0, [
                        new_measure(withings.MEASURE_TYPE_WEIGHT, 70, 0),
                        new_measure(withings.MEASURE_TYPE_FAT_MASS, 5, 0),
                        new_measure(
                            withings.MEASURE_TYPE_FAT_MASS_FREE, 60, 0
                        ),
                        new_measure(withings.MEASURE_TYPE_MUSCLE_MASS, 50, 0),
                        new_measure(withings.MEASURE_TYPE_BONE_MASS, 10, 0),
                        new_measure(withings.MEASURE_TYPE_HEIGHT, 2, 0),
                        new_measure(withings.MEASURE_TYPE_TEMP, 40, 0),
                        new_measure(withings.MEASURE_TYPE_BODY_TEMP, 35, 0),
                        new_measure(withings.MEASURE_TYPE_SKIN_TEMP, 20, 0),
                        new_measure(withings.MEASURE_TYPE_FAT_RATIO, 70, -3),
                        new_measure(withings.MEASURE_TYPE_DIASTOLIC_BP, 70, 0),
                        new_measure(withings.MEASURE_TYPE_SYSTOLIC_BP, 100, 0),
                        new_measure(withings.MEASURE_TYPE_HEART_PULSE, 60, 0),
                        new_measure(withings.MEASURE_TYPE_SPO2, 95, -2),
                        new_measure(withings.MEASURE_TYPE_HYDRATION, 95, -2),
                        new_measure(withings.MEASURE_TYPE_PWV, 100, 0),
                    ]
                ),

                # Ambiguous groups (we ignore these)
                new_measure_group(
                    1, 1, time.time(), time.time(), 1, 'DEV_ID', False, 0, [
                        new_measure(withings.MEASURE_TYPE_WEIGHT, 71, 0),
                        new_measure(withings.MEASURE_TYPE_FAT_MASS, 4, 0),
                        new_measure(withings.MEASURE_TYPE_MUSCLE_MASS, 51, 0),
                        new_measure(withings.MEASURE_TYPE_BONE_MASS, 11, 0),
                        new_measure(withings.MEASURE_TYPE_HEIGHT, 201, 0),
                        new_measure(withings.MEASURE_TYPE_TEMP, 41, 0),
                        new_measure(withings.MEASURE_TYPE_BODY_TEMP, 34, 0),
                        new_measure(withings.MEASURE_TYPE_SKIN_TEMP, 21, 0),
                        new_measure(withings.MEASURE_TYPE_FAT_RATIO, 71, -3),
                        new_measure(withings.MEASURE_TYPE_DIASTOLIC_BP, 71, 0),
                        new_measure(withings.MEASURE_TYPE_SYSTOLIC_BP, 101, 0),
                        new_measure(withings.MEASURE_TYPE_HEART_PULSE, 61, 0),
                        new_measure(withings.MEASURE_TYPE_SPO2, 98, -2),
                        new_measure(withings.MEASURE_TYPE_HYDRATION, 96, -2),
                        new_measure(withings.MEASURE_TYPE_PWV, 102, 0),
                    ]
                )
            ],
            'more': False,
            'offset': 0
        })

        await self.assert_sensor_equals(70, withings.MEAS_WEIGHT_KG)
        await self.assert_sensor_equals(154.35, withings.MEAS_WEIGHT_LB)
        await self.assert_sensor_equals(5, withings.MEAS_FAT_MASS_KG)
        await self.assert_sensor_equals(11.03, withings.MEAS_FAT_MASS_LB)
        await self.assert_sensor_equals(60, withings.MEAS_FAT_FREE_MASS_KG)
        await self.assert_sensor_equals(132.3, withings.MEAS_FAT_FREE_MASS_LB)
        await self.assert_sensor_equals(50, withings.MEAS_MUSCLE_MASS_KG)
        await self.assert_sensor_equals(110.25, withings.MEAS_MUSCLE_MASS_LB)
        await self.assert_sensor_equals(10, withings.MEAS_BONE_MASS_KG)
        await self.assert_sensor_equals(22.05, withings.MEAS_BONE_MASS_LB)
        await self.assert_sensor_equals(2, withings.MEAS_HEIGHT_M)
        await self.assert_sensor_equals(200, withings.MEAS_HEIGHT_CM)
        await self.assert_sensor_equals(78.74, withings.MEAS_HEIGHT_IN)
        await self.assert_sensor_equals('6\' 6"', withings.MEAS_HEIGHT_IMP)
        await self.assert_sensor_equals(40, withings.MEAS_TEMP_C)
        await self.assert_sensor_equals(104, withings.MEAS_TEMP_F)
        await self.assert_sensor_equals(35, withings.MEAS_BODY_TEMP_C)
        await self.assert_sensor_equals(95.0, withings.MEAS_BODY_TEMP_F)
        await self.assert_sensor_equals(20, withings.MEAS_SKIN_TEMP_C)
        await self.assert_sensor_equals(68.0, withings.MEAS_SKIN_TEMP_F)
        await self.assert_sensor_equals(7.0, withings.MEAS_FAT_RATIO_PCT)
        await self.assert_sensor_equals(70, withings.MEAS_DIASTOLIC_MMHG)
        await self.assert_sensor_equals(100, withings.MEAS_SYSTOLIC_MMGH)
        await self.assert_sensor_equals(60, withings.MEAS_HEART_PULSE_BPM)
        await self.assert_sensor_equals(95.0, withings.MEAS_SPO2_PCT)
        await self.assert_sensor_equals(0.95, withings.MEAS_HYDRATION)
        await self.assert_sensor_equals(100, withings.MEAS_PWV)

        self.recreate_data_manager()
        self.api.get_sleep.return_value = nokia.NokiaSleep(new_sleep_data(
            'aa',
            [
                new_sleep_data_serie(
                    '2019-02-01 00:00:00',
                    '2019-02-01 00:30:00',
                    withings.MEASURE_TYPE_SLEEP_STATE_AWAKE
                ),
                new_sleep_data_serie(
                    '2019-02-01 02:00:00',
                    '2019-02-01 02:30:00',
                    withings.MEASURE_TYPE_SLEEP_STATE_DEEP
                ),
                new_sleep_data_serie(
                    '2019-02-01 01:00:00',
                    '2019-02-01 01:30:00',
                    withings.MEASURE_TYPE_SLEEP_STATE_REM
                ),
            ]
        ))
        await self.assert_sensor_equals(
            withings.STATE_DEEP,
            withings.MEAS_SLEEP_STATE
        )

        self.recreate_data_manager()
        self.api.get_sleep.return_value = nokia.NokiaSleep(new_sleep_data(
            'aa',
            [
                new_sleep_data_serie(
                    '2019-02-01 00:00:00',
                    '2019-02-01 00:30:00',
                    withings.MEASURE_TYPE_SLEEP_STATE_AWAKE
                ),
            ]
        ))
        await self.assert_sensor_equals(
            withings.STATE_AWAKE,
            withings.MEAS_SLEEP_STATE
        )

        self.recreate_data_manager()
        self.api.get_sleep.return_value = nokia.NokiaSleep(new_sleep_data(
            'aa',
            [
                new_sleep_data_serie(
                    '2019-02-01 00:00:00',
                    '2019-02-01 00:30:00',
                    withings.MEASURE_TYPE_SLEEP_STATE_LIGHT
                ),
            ]
        ))
        await self.assert_sensor_equals(
            withings.STATE_LIGHT,
            withings.MEAS_SLEEP_STATE
        )

        self.recreate_data_manager()
        self.api.get_sleep.return_value = nokia.NokiaSleep(new_sleep_data(
            'aa',
            [
                new_sleep_data_serie(
                    '2019-02-01 00:00:00',
                    '2019-02-01 00:30:00',
                    withings.MEASURE_TYPE_SLEEP_STATE_DEEP
                ),
            ]
        ))
        await self.assert_sensor_equals(
            withings.STATE_DEEP,
            withings.MEAS_SLEEP_STATE
        )

        self.recreate_data_manager()
        self.api.get_sleep.return_value = nokia.NokiaSleep(new_sleep_data(
            'aa',
            [
                new_sleep_data_serie(
                    '2019-02-01 00:00:00',
                    '2019-02-01 00:30:00',
                    withings.MEASURE_TYPE_SLEEP_STATE_REM
                ),
            ]
        ))
        await self.assert_sensor_equals(
            withings.STATE_REM,
            withings.MEAS_SLEEP_STATE
        )

        self.recreate_data_manager()
        self.api.get_sleep.return_value = None
        await self.assert_sensor_equals(
            withings.STATE_UNKNOWN,
            withings.MEAS_SLEEP_STATE
        )

        self.recreate_data_manager()
        self.api.get_sleep.return_value = nokia.NokiaSleep(
            new_sleep_data('aa', [])
        )
        await self.assert_sensor_equals(
            withings.STATE_UNKNOWN,
            withings.MEAS_SLEEP_STATE
        )

        self.api.get_sleep_summary.return_value = nokia.NokiaSleepSummary({
            'series': [
                new_sleep_summary(
                    'UTC',
                    32,
                    '2019-02-01',
                    '2019-02-02',
                    '2019-02-02',
                    '12345',
                    new_sleep_summary_detail(
                        110,
                        210,
                        310,
                        410,
                        510,
                        610,
                        710,
                        810,
                        910,
                        1010,
                        1110,
                        1210,
                        1310
                    ),
                ),
                new_sleep_summary(
                    'UTC',
                    32,
                    '2019-02-01',
                    '2019-02-02',
                    '2019-02-02',
                    '12345',
                    new_sleep_summary_detail(
                        210,
                        310,
                        410,
                        510,
                        610,
                        710,
                        810,
                        910,
                        1010,
                        1110,
                        1210,
                        1310,
                        1410
                    ),
                )
            ]
        })

        await self.assert_sensor_equals(
            2.7, withings.MEAS_SLEEP_WAKEUP_DURATION_HOURS
        )
        await self.assert_sensor_equals(
            4.3, withings.MEAS_SLEEP_LIGHT_DURATION_HOURS
        )
        await self.assert_sensor_equals(
            6.0, withings.MEAS_SLEEP_DEEP_DURATION_HOURS
        )
        await self.assert_sensor_equals(
            7.7, withings.MEAS_SLEEP_REM_DURATION_HOURS
        )
        await self.assert_sensor_equals(
            160.0,
            withings.MEAS_SLEEP_WAKEUP_DURATION_MINUTES
        )
        await self.assert_sensor_equals(
            260.0,
            withings.MEAS_SLEEP_LIGHT_DURATION_MINUTES
        )
        await self.assert_sensor_equals(
            360,
            withings.MEAS_SLEEP_DEEP_DURATION_MINUTES
        )
        await self.assert_sensor_equals(
            460.0,
            withings.MEAS_SLEEP_REM_DURATION_MINUTES
        )
        await self.assert_sensor_equals(
            560.0,
            withings.MEAS_SLEEP_WAKEUP_COUNT
        )
        await self.assert_sensor_equals(
            11.0,
            withings.MEAS_SLEEP_TOSLEEP_DURATION_HOURS
        )
        await self.assert_sensor_equals(
            12.7,
            withings.MEAS_SLEEP_TOWAKEUP_DURATION_HOURS
        )
        await self.assert_sensor_equals(
            660.0,
            withings.MEAS_SLEEP_TOSLEEP_DURATION_MINUTES
        )
        await self.assert_sensor_equals(
            760.0,
            withings.MEAS_SLEEP_TOWAKEUP_DURATION_MINUTES
        )
        await self.assert_sensor_equals(
            860.0,
            withings.MEAS_SLEEP_HEART_RATE_AVERAGE
        )
        await self.assert_sensor_equals(
            960.0,
            withings.MEAS_SLEEP_HEART_RATE_MIN
        )
        await self.assert_sensor_equals(
            1060.0,
            withings.MEAS_SLEEP_HEART_RATE_MAX
        )
        await self.assert_sensor_equals(
            1160.0,
            withings.MEAS_SLEEP_RESPIRATORY_RATE_AVERAGE
        )
        await self.assert_sensor_equals(
            1260.0,
            withings.MEAS_SLEEP_RESPIRATORY_RATE_MIN
        )
        await self.assert_sensor_equals(
            1360.0,
            withings.MEAS_SLEEP_RESPIRATORY_RATE_MAX
        )

    async def assert_sensor_equals(self, expected, measure):
        """Assert the state of a withings sensor."""
        sensor = withings.WithingsHealthSensor(
            self.data_manager,
            withings.WITHINGS_MEASUREMENTS_MAP[measure]
        )

        await sensor.async_update()
        assert sensor.state == expected, \
            'Expected %s but was %s for measure: %s.' % (
                expected,
                sensor.state,
                measure
            )


def new_sleep_data(model, series):
    """Create simple dict to simulate api data."""
    return {
        'series': series,
        'model': model
    }


def new_sleep_data_serie(startdate, enddate, state):
    """Create simple dict to simulate api data."""
    return {
        'startdate': startdate,
        'enddate': enddate,
        'state': state
    }


def new_sleep_summary(timezone,
                      model,
                      startdate,
                      enddate,
                      date,
                      modified,
                      data):
    """Create simple dict to simulate api data."""
    return {
        'timezone': timezone,
        'model': model,
        'startdate': startdate,
        'enddate': enddate,
        'date': date,
        'modified': modified,
        'data': data,
    }


def new_sleep_summary_detail(wakeupduration,
                             lightsleepduration,
                             deepsleepduration,
                             remsleepduration,
                             wakeupcount,
                             durationtosleep,
                             durationtowakeup,
                             hr_average,
                             hr_min,
                             hr_max,
                             rr_average,
                             rr_min,
                             rr_max):
    """Create simple dict to simulate api data."""
    return {
        'wakeupduration': wakeupduration,
        'lightsleepduration': lightsleepduration,
        'deepsleepduration': deepsleepduration,
        'remsleepduration': remsleepduration,
        'wakeupcount': wakeupcount,
        'durationtosleep': durationtosleep,
        'durationtowakeup': durationtowakeup,
        'hr_average': hr_average,
        'hr_min': hr_min,
        'hr_max': hr_max,
        'rr_average': rr_average,
        'rr_min': rr_min,
        'rr_max': rr_max,
    }


def new_measure_group(grpid,
                      attrib,
                      date,
                      created,
                      category,
                      deviceid,
                      more,
                      offset,
                      measures):
    """Create simple dict to simulate api data."""
    return {
        'grpid': grpid,
        'attrib': attrib,
        'date': date,
        'created': created,
        'category': category,
        'deviceid': deviceid,
        'measures': measures,
        'more': more,
        'offset': offset,
        'comment': 'blah'  # deprecated
    }


def new_measure(type_str, value, unit):
    """Create simple dict to simulate api data."""
    return {
        'value': value,
        'type': type_str,
        'unit': unit,
        'algo': -1,  # deprecated
        'fm': -1,  # deprecated
        'fw': -1  # deprecated
    }
