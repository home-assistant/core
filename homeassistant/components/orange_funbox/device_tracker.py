"""Support for Orange FunBox router."""
from collections import namedtuple
import logging
from typing import Any, Dict, List, Optional

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import (
    HomeAssistantType,
    ConfigType,
)
import homeassistant.util.dt as dt_util
from homeassistant.components.device_tracker import (
    DOMAIN,
    PLATFORM_SCHEMA,
    DeviceScanner,
)
from homeassistant.const import CONF_HOST

_LOGGER = logging.getLogger(__name__)

CONF_EXCLUDE = 'exclude'


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_EXCLUDE, default=[]):
        vol.All(cv.ensure_list, [cv.string]),
})


Device = namedtuple(
    'Device',
    [
        'active',
        'device_type',
        'first_seen',
        'ip',
        'last_connection',
        'last_update',
        'mac',
        'name',
        'signal_noise_ratio',
        'signal_strength',
    ],
)


class FunboxDeviceScanner(DeviceScanner):
    """Device tracker for Orange FunBox 3."""

    def __init__(self, config: ConfigType) -> None:
        """Init."""
        self.last_results = []

        self.host = config[CONF_HOST]
        self.exclude = config[CONF_EXCLUDE]

        _LOGGER.debug('Scanner initialized')

    def scan_devices(self) -> List[str]:
        """Update list of devices from FunBox API."""
        self._update_info()
        return [
            device.mac
            for device in self.last_results
        ]

    def get_device_name(self, device: str) -> Optional[str]:
        """Return the name of the given device or None."""
        result = next(
            (
                result for result in self.last_results
                if result.mac == device
            ),
            None,
        )
        return result.name if result else None

    def get_extra_attributes(self, device: str) -> Optional[Dict[str, Any]]:
        """Return all the attributes of the given device."""
        result = next(
            (
                result for result in self.last_results
                if result.mac == device
            ),
            None,
        )
        return result._asdict() if result else None

    def _update_info(self) -> bool:
        """Request list of devices from FunBox API."""
        _LOGGER.debug('Getting devices')

        path = '/sysbus/Devices:get'
        resp = requests.post('http://{0}{1}'.format(self.host, path))

        devices_data = resp.json()['status']

        new_results = []

        for device_data in devices_data:
            mac = device_data.get('PhysAddress', None)

            if not mac or mac in self.exclude:
                continue

            active = device_data.get('Active', False)

            if not active:
                continue

            name = device_data.get('Name')
            ipv4 = device_data.get('IPAddress')
            first_seen = device_data.get('FirstSeen')
            last_connection = device_data.get('LastConnection')
            last_update = dt_util.utcnow()
            device_type = device_data.get('DeviceType')
            signal_strength = device_data.get('SignalStrength')
            signal_noise_ratio = device_data.get('SignalNoiseRatio')

            new_results.append(Device(
                active=active,
                device_type=device_type,
                first_seen=first_seen,
                ip=ipv4,
                last_connection=last_connection,
                last_update=last_update,
                mac=mac.upper(),
                name=name,
                signal_noise_ratio=signal_noise_ratio,
                signal_strength=signal_strength,
            ))

        self.last_results = new_results

        _LOGGER.debug('FunBox devices updated')
        return True


def get_scanner(
        hass: HomeAssistantType, config: ConfigType) -> FunboxDeviceScanner:
    """Build FunboxDeviceScanner."""
    return FunboxDeviceScanner(config[DOMAIN])
