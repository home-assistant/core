"""
Support for ZoneMinder camera streaming.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.zoneminder/
"""
import asyncio
import logging
from urllib.parse import urljoin, urlencode

from homeassistant.const import CONF_NAME
from homeassistant.components.camera.mjpeg import (
    CONF_MJPEG_URL, CONF_STILL_IMAGE_URL, MjpegCamera)

import homeassistant.components.zoneminder as zoneminder

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['zoneminder']
DOMAIN = 'zoneminder'


def _get_image_url(hass, monitor, mode):
    zm_data = hass.data[DOMAIN]
    query = urlencode({
        'mode': mode,
        'buffer': monitor['StreamReplayBuffer'],
        'monitor': monitor['Id'],
    })
    url = '{zms_url}?{query}'.format(
        zms_url=urljoin(zm_data['server_origin'], zm_data['path_zms']),
        query=query,
    )
    _LOGGER.debug('Monitor %s %s URL (without auth): %s',
                  monitor['Id'], mode, url)

    if not zm_data['username']:
        return url

    url += '&user={:s}'.format(zm_data['username'])

    if not zm_data['password']:
        return url

    return url + '&pass={:s}'.format(zm_data['password'])


@asyncio.coroutine
# pylint: disable=unused-argument
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup ZoneMinder cameras."""
    cameras = []
    monitors = zoneminder.get_state('api/monitors.json')
    if not monitors:
        _LOGGER.warning('Could not fetch monitors from ZoneMinder')
        return

    for i in monitors['monitors']:
        monitor = i['Monitor']

        if monitor['Function'] == 'None':
            _LOGGER.info('Skipping camera %s', monitor['Id'])
            continue

        _LOGGER.info('Initializing camera %s', monitor['Id'])

        device_info = {
            CONF_NAME: monitor['Name'],
            CONF_MJPEG_URL: _get_image_url(hass, monitor, 'jpeg'),
            CONF_STILL_IMAGE_URL: _get_image_url(hass, monitor, 'single')
        }
        cameras.append(MjpegCamera(hass, device_info))

    if not cameras:
        _LOGGER.warning('No active cameras found')
        return

    async_add_devices(cameras)
