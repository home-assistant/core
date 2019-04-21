"""Tests for the Withings component."""
import time
import datetime
import nokia
import callee
from asynctest import patch, MagicMock
from homeassistant.components.withings import (
    async_setup,
    WithingsDataManager,
    WithingsHealthSensor,
    WITHINGS_MEASUREMENTS_MAP
)
import homeassistant.components.withings.const as const
from homeassistant.components.withings.config_flow import DATA_FLOW_IMPL
from homeassistant.setup import async_setup_component
import homeassistant.components.http as http
import homeassistant.components.api as api
from tests.common import get_test_home_assistant


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
            context={'source': const.SOURCE_PROFILE},
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


class TestWithingsDataManager:
    """Tests the data manager class."""

    def setup_method(self):
        """Set up the test."""
        self.hass = get_test_home_assistant()
        self.api = nokia.NokiaApi.__new__(nokia.NokiaApi)
        self.api.get_measures = MagicMock()
        self.api.get_sleep = MagicMock()

    def teardown_method(self):
        """Tear down the test."""
        self.hass.stop()

    async def test_async_update_measures(self):
        """Test method."""
        data_manager = WithingsDataManager(
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

    async def test_async_update_sleep(self):
        """Test method."""
        data_manager = WithingsDataManager(
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

    async def test_async_update_sleep_summary(self):
        """Test method."""
        now = datetime.datetime.utcnow()
        noon = datetime.datetime(
            now.year, now.month, now.day,
            12, 0, 0, 0,
            datetime.timezone.utc
        )
        yesterday_noon_timestamp = noon.timestamp() - 86400

        data_manager = WithingsDataManager(
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


class TestWithingsHealthSensor:
    """Tests all the health sensors."""

    def setup_method(self):
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

    def teardown_method(self):
        """Tear down the test."""
        self.hass.stop()

    def recreate_data_manager(self):
        """Recreate data manager to get arround the @Trottle decorators."""
        self.data_manager = WithingsDataManager(
            'person_1',
            self.api
        )

    def test_properties(self):
        """Test method."""
        sensor = WithingsHealthSensor(
            self.data_manager,
            WITHINGS_MEASUREMENTS_MAP[const.MEAS_WEIGHT_KG]
        )

        assert sensor.name == 'Withings weight_kg person_1'
        assert sensor.unique_id == 'withings_person_1_USER_ID_weight_kg'
        assert sensor.state is None
        assert sensor.unit_of_measurement == 'kg'
        assert sensor.icon == 'mdi:weight-kilogram'

    async def test_async_update(self):
        """Test method."""
        self.api.get_measures.return_value = nokia.NokiaMeasures({
            'updatetime': '',
            'timezone': '',
            'measuregrps': [
                # Un-ambiguous groups.
                new_measure_group(
                    1, 0, time.time(), time.time(), 1, 'DEV_ID', False, 0, [
                        new_measure(const.MEASURE_TYPE_WEIGHT, 70, 0),
                        new_measure(const.MEASURE_TYPE_FAT_MASS, 5, 0),
                        new_measure(
                            const.MEASURE_TYPE_FAT_MASS_FREE, 60, 0
                        ),
                        new_measure(const.MEASURE_TYPE_MUSCLE_MASS, 50, 0),
                        new_measure(const.MEASURE_TYPE_BONE_MASS, 10, 0),
                        new_measure(const.MEASURE_TYPE_HEIGHT, 2, 0),
                        new_measure(const.MEASURE_TYPE_TEMP, 40, 0),
                        new_measure(const.MEASURE_TYPE_BODY_TEMP, 35, 0),
                        new_measure(const.MEASURE_TYPE_SKIN_TEMP, 20, 0),
                        new_measure(const.MEASURE_TYPE_FAT_RATIO, 70, -3),
                        new_measure(const.MEASURE_TYPE_DIASTOLIC_BP, 70, 0),
                        new_measure(const.MEASURE_TYPE_SYSTOLIC_BP, 100, 0),
                        new_measure(const.MEASURE_TYPE_HEART_PULSE, 60, 0),
                        new_measure(const.MEASURE_TYPE_SPO2, 95, -2),
                        new_measure(const.MEASURE_TYPE_HYDRATION, 95, -2),
                        new_measure(const.MEASURE_TYPE_PWV, 100, 0),
                    ]
                ),

                # Ambiguous groups (we ignore these)
                new_measure_group(
                    1, 1, time.time(), time.time(), 1, 'DEV_ID', False, 0, [
                        new_measure(const.MEASURE_TYPE_WEIGHT, 71, 0),
                        new_measure(const.MEASURE_TYPE_FAT_MASS, 4, 0),
                        new_measure(const.MEASURE_TYPE_MUSCLE_MASS, 51, 0),
                        new_measure(const.MEASURE_TYPE_BONE_MASS, 11, 0),
                        new_measure(const.MEASURE_TYPE_HEIGHT, 201, 0),
                        new_measure(const.MEASURE_TYPE_TEMP, 41, 0),
                        new_measure(const.MEASURE_TYPE_BODY_TEMP, 34, 0),
                        new_measure(const.MEASURE_TYPE_SKIN_TEMP, 21, 0),
                        new_measure(const.MEASURE_TYPE_FAT_RATIO, 71, -3),
                        new_measure(const.MEASURE_TYPE_DIASTOLIC_BP, 71, 0),
                        new_measure(const.MEASURE_TYPE_SYSTOLIC_BP, 101, 0),
                        new_measure(const.MEASURE_TYPE_HEART_PULSE, 61, 0),
                        new_measure(const.MEASURE_TYPE_SPO2, 98, -2),
                        new_measure(const.MEASURE_TYPE_HYDRATION, 96, -2),
                        new_measure(const.MEASURE_TYPE_PWV, 102, 0),
                    ]
                )
            ],
            'more': False,
            'offset': 0
        })

        await self.assert_sensor_equals(70, const.MEAS_WEIGHT_KG)
        await self.assert_sensor_equals(154.35, const.MEAS_WEIGHT_LB)
        await self.assert_sensor_equals(11.02, const.MEAS_WEIGHT_STONE)
        await self.assert_sensor_equals(5, const.MEAS_FAT_MASS_KG)
        await self.assert_sensor_equals(11.03, const.MEAS_FAT_MASS_LB)
        await self.assert_sensor_equals(60, const.MEAS_FAT_FREE_MASS_KG)
        await self.assert_sensor_equals(132.3, const.MEAS_FAT_FREE_MASS_LB)
        await self.assert_sensor_equals(50, const.MEAS_MUSCLE_MASS_KG)
        await self.assert_sensor_equals(110.25, const.MEAS_MUSCLE_MASS_LB)
        await self.assert_sensor_equals(10, const.MEAS_BONE_MASS_KG)
        await self.assert_sensor_equals(22.05, const.MEAS_BONE_MASS_LB)
        await self.assert_sensor_equals(2, const.MEAS_HEIGHT_M)
        await self.assert_sensor_equals(200, const.MEAS_HEIGHT_CM)
        await self.assert_sensor_equals(78.74, const.MEAS_HEIGHT_IN)
        await self.assert_sensor_equals('6\' 6"', const.MEAS_HEIGHT_IMP)
        await self.assert_sensor_equals(40, const.MEAS_TEMP_C)
        await self.assert_sensor_equals(104, const.MEAS_TEMP_F)
        await self.assert_sensor_equals(35, const.MEAS_BODY_TEMP_C)
        await self.assert_sensor_equals(95.0, const.MEAS_BODY_TEMP_F)
        await self.assert_sensor_equals(20, const.MEAS_SKIN_TEMP_C)
        await self.assert_sensor_equals(68.0, const.MEAS_SKIN_TEMP_F)
        await self.assert_sensor_equals(7.0, const.MEAS_FAT_RATIO_PCT)
        await self.assert_sensor_equals(70, const.MEAS_DIASTOLIC_MMHG)
        await self.assert_sensor_equals(100, const.MEAS_SYSTOLIC_MMGH)
        await self.assert_sensor_equals(60, const.MEAS_HEART_PULSE_BPM)
        await self.assert_sensor_equals(95.0, const.MEAS_SPO2_PCT)
        await self.assert_sensor_equals(0.95, const.MEAS_HYDRATION)
        await self.assert_sensor_equals(100, const.MEAS_PWV)

        self.recreate_data_manager()
        self.api.get_sleep.return_value = nokia.NokiaSleep(new_sleep_data(
            'aa',
            [
                new_sleep_data_serie(
                    '2019-02-01 00:00:00',
                    '2019-02-01 00:30:00',
                    const.MEASURE_TYPE_SLEEP_STATE_AWAKE
                ),
                new_sleep_data_serie(
                    '2019-02-01 02:00:00',
                    '2019-02-01 02:30:00',
                    const.MEASURE_TYPE_SLEEP_STATE_DEEP
                ),
                new_sleep_data_serie(
                    '2019-02-01 01:00:00',
                    '2019-02-01 01:30:00',
                    const.MEASURE_TYPE_SLEEP_STATE_REM
                ),
            ]
        ))
        await self.assert_sensor_equals(
            const.STATE_DEEP,
            const.MEAS_SLEEP_STATE
        )

        self.recreate_data_manager()
        self.api.get_sleep.return_value = nokia.NokiaSleep(new_sleep_data(
            'aa',
            [
                new_sleep_data_serie(
                    '2019-02-01 00:00:00',
                    '2019-02-01 00:30:00',
                    const.MEASURE_TYPE_SLEEP_STATE_AWAKE
                ),
            ]
        ))
        await self.assert_sensor_equals(
            const.STATE_AWAKE,
            const.MEAS_SLEEP_STATE
        )

        self.recreate_data_manager()
        self.api.get_sleep.return_value = nokia.NokiaSleep(new_sleep_data(
            'aa',
            [
                new_sleep_data_serie(
                    '2019-02-01 00:00:00',
                    '2019-02-01 00:30:00',
                    const.MEASURE_TYPE_SLEEP_STATE_LIGHT
                ),
            ]
        ))
        await self.assert_sensor_equals(
            const.STATE_LIGHT,
            const.MEAS_SLEEP_STATE
        )

        self.recreate_data_manager()
        self.api.get_sleep.return_value = nokia.NokiaSleep(new_sleep_data(
            'aa',
            [
                new_sleep_data_serie(
                    '2019-02-01 00:00:00',
                    '2019-02-01 00:30:00',
                    const.MEASURE_TYPE_SLEEP_STATE_DEEP
                ),
            ]
        ))
        await self.assert_sensor_equals(
            const.STATE_DEEP,
            const.MEAS_SLEEP_STATE
        )

        self.recreate_data_manager()
        self.api.get_sleep.return_value = nokia.NokiaSleep(new_sleep_data(
            'aa',
            [
                new_sleep_data_serie(
                    '2019-02-01 00:00:00',
                    '2019-02-01 00:30:00',
                    const.MEASURE_TYPE_SLEEP_STATE_REM
                ),
            ]
        ))
        await self.assert_sensor_equals(
            const.STATE_REM,
            const.MEAS_SLEEP_STATE
        )

        self.recreate_data_manager()
        self.api.get_sleep.return_value = None
        await self.assert_sensor_equals(
            const.STATE_UNKNOWN,
            const.MEAS_SLEEP_STATE
        )

        self.recreate_data_manager()
        self.api.get_sleep.return_value = nokia.NokiaSleep(
            new_sleep_data('aa', [])
        )
        await self.assert_sensor_equals(
            const.STATE_UNKNOWN,
            const.MEAS_SLEEP_STATE
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
            2.7, const.MEAS_SLEEP_WAKEUP_DURATION_HOURS
        )
        await self.assert_sensor_equals(
            4.3, const.MEAS_SLEEP_LIGHT_DURATION_HOURS
        )
        await self.assert_sensor_equals(
            6.0, const.MEAS_SLEEP_DEEP_DURATION_HOURS
        )
        await self.assert_sensor_equals(
            7.7, const.MEAS_SLEEP_REM_DURATION_HOURS
        )
        await self.assert_sensor_equals(
            160.0,
            const.MEAS_SLEEP_WAKEUP_DURATION_MINUTES
        )
        await self.assert_sensor_equals(
            260.0,
            const.MEAS_SLEEP_LIGHT_DURATION_MINUTES
        )
        await self.assert_sensor_equals(
            360,
            const.MEAS_SLEEP_DEEP_DURATION_MINUTES
        )
        await self.assert_sensor_equals(
            460.0,
            const.MEAS_SLEEP_REM_DURATION_MINUTES
        )
        await self.assert_sensor_equals(
            560.0,
            const.MEAS_SLEEP_WAKEUP_COUNT
        )
        await self.assert_sensor_equals(
            11.0,
            const.MEAS_SLEEP_TOSLEEP_DURATION_HOURS
        )
        await self.assert_sensor_equals(
            12.7,
            const.MEAS_SLEEP_TOWAKEUP_DURATION_HOURS
        )
        await self.assert_sensor_equals(
            660.0,
            const.MEAS_SLEEP_TOSLEEP_DURATION_MINUTES
        )
        await self.assert_sensor_equals(
            760.0,
            const.MEAS_SLEEP_TOWAKEUP_DURATION_MINUTES
        )
        await self.assert_sensor_equals(
            860.0,
            const.MEAS_SLEEP_HEART_RATE_AVERAGE
        )
        await self.assert_sensor_equals(
            960.0,
            const.MEAS_SLEEP_HEART_RATE_MIN
        )
        await self.assert_sensor_equals(
            1060.0,
            const.MEAS_SLEEP_HEART_RATE_MAX
        )
        await self.assert_sensor_equals(
            1160.0,
            const.MEAS_SLEEP_RESPIRATORY_RATE_AVERAGE
        )
        await self.assert_sensor_equals(
            1260.0,
            const.MEAS_SLEEP_RESPIRATORY_RATE_MIN
        )
        await self.assert_sensor_equals(
            1360.0,
            const.MEAS_SLEEP_RESPIRATORY_RATE_MAX
        )

    async def assert_sensor_equals(self, expected, measure):
        """Assert the state of a withings sensor."""
        sensor = WithingsHealthSensor(
            self.data_manager,
            WITHINGS_MEASUREMENTS_MAP[measure]
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
