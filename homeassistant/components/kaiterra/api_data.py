from logging import getLogger

import async_timeout

from homeassistant.helpers.dispatcher import (
    async_dispatcher_send,
)

from homeassistant.const import (
    CONF_API_KEY,
    CONF_DEVICES,
    CONF_DEVICE_ID,
    CONF_SCAN_INTERVAL,
    CONF_TYPE,
    CONF_NAME,
)

from .const import (
    AQI_SCALE,
    AQI_LEVEL,
    CONF_AQI_STANDARD,
    CONF_PREFERRED_UNITS,
    KAITERRA_COMPONENTS,
    DISPATCHER_KAITERRA
)

_LOGGER = getLogger(__name__)

POLLUTANTS = {
    'rpm25c': 'PM2.5',
    'rpm10c': 'PM10',
    'rtvoc': 'TVOC'
}


class KaiterraApiData:
    """Get data from Kaiterra API."""

    def __init__(self, hass, config, session):
        """Initialize the API data object."""

        api_key = config.get(CONF_API_KEY)
        aqi_standard = config.get(CONF_AQI_STANDARD)
        devices = config.get(CONF_DEVICES)
        units = config.get(CONF_PREFERRED_UNITS)

        self._hass = hass
        self._api = self._create_api_client(session, api_key, aqi_standard, units)
        self._devices_ids = [device.get(CONF_DEVICE_ID) for device in devices]
        self._devices = [f'/{device.get(CONF_TYPE)}s/{device.get(CONF_DEVICE_ID)}' for device in devices]
        self._scale = AQI_SCALE[aqi_standard]
        self._level = AQI_LEVEL[aqi_standard]
        self._update_listeners = []
        self.data = {}

    def _create_api_client(self, session, api_key, aqi_standard, units):
        """Creates the Kaiterra API client"""
        from kaiterra_async_client import KaiterraAPIClient, AQIStandard, Units
        return KaiterraAPIClient(session, api_key=api_key, aqi_standard=AQIStandard.from_str(aqi_standard), preferred_units=[Units.from_str(unit) for unit in units])

    async def async_update(self) -> None:
        """Get the data from Kaiterra API."""

        try:
            with async_timeout.timeout(10):
                data = await self._api.get_latest_sensor_readings(self._devices)
                _LOGGER.debug('New data retrieved: %s', data)
        except:
            _LOGGER.debug("Couldn't fetch data")
            self.data = {}
            async_dispatcher_send(self._hass, DISPATCHER_KAITERRA)
            return False

        try:
            self.data = {}
            for i in range(len(data)):
                device = data[i]

                if not device:
                    self.data[self._devices_ids[i]] = {}
                    continue

                aqi, main_pollutant = None, None
                for sensor in device:
                    points = device.get(sensor).get('points')

                    if not points or len(points) == 0:
                        continue

                    point = points[0]
                    device[sensor]['value'] = point.get('value')

                    if 'aqi' not in point:
                        continue

                    device[sensor]['aqi'] = point.get('aqi')
                    if not aqi or aqi < point.get('aqi'):
                        aqi = point['aqi']
                        main_pollutant = POLLUTANTS.get(sensor)

                level = None
                for j in range(1, len(self._scale)):
                    if aqi <= self._scale[j]:
                        level = self._level[j - 1]
                        break

                device['aqi'] = {'value': aqi}
                device['aqi_level'] = {'value': level}
                device['aqi_pollutant'] = {'value': main_pollutant}

                self.data[self._devices_ids[i]] = device

                async_dispatcher_send(self._hass, DISPATCHER_KAITERRA)
        except IndexError as err:
            _LOGGER.error('Parsing error %s', err)
            async_dispatcher_send(self._hass, DISPATCHER_KAITERRA)
            return False
        return True
