"""Tests for the Withings sensor platform."""
from asynctest import patch, MagicMock
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.withings.sensor import async_setup_entry
import homeassistant.components.withings.const as const
from homeassistant.components.withings import (
    WithingsDataManager,
    WithingsHealthSensor
)


async def test_async_setup_entry(hass):
    """Test setup of config entry."""
    import nokia
    nokia_api_patch = patch('nokia.NokiaApi')
    withings_data_manager_patch = patch(
        'homeassistant.components.withings.sensor.WithingsDataManager'
    )
    withings_health_sensor_patch = patch(
        'homeassistant.components.withings.WithingsHealthSensor'
    )

    with nokia_api_patch as nokia_api_mock, \
        withings_data_manager_patch as data_manager_mock, \
            withings_health_sensor_patch as health_sensor_mock:

        async def async_refresh_token():
            pass

        nokia_api_instance = MagicMock(spec=nokia.NokiaApi)
        nokia_api_instance.get_user = MagicMock()

        data_manager_instance = MagicMock(spec=WithingsDataManager)
        data_manager_instance.async_refresh_token = async_refresh_token

        nokia_api_mock.return_value = nokia_api_instance
        data_manager_mock.return_value = data_manager_instance
        health_sensor_mock.return_value = MagicMock(spec=WithingsHealthSensor)

        async_add_entities = MagicMock()
        config_entry = ConfigEntry(
            'version',
            'domain',
            'title',
            {
                const.PROFILE: 'Person 1',
                const.CREDENTIALS: 'my_credentials',
            },
            'source',
            'connection_class'
        )

        result = await async_setup_entry(
            hass,
            config_entry,
            async_add_entities
        )

        assert result
