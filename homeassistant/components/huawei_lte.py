"""
Support for Huawei LTE routers.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/huawei_lte/
"""
from datetime import timedelta
from functools import reduce
import logging
import operator

import voluptuous as vol
import attr

from homeassistant.const import (
    CONF_URL, CONF_USERNAME, CONF_PASSWORD, EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.util import Throttle


_LOGGER = logging.getLogger(__name__)

# dicttoxml (used by huawei-lte-api) has uselessly verbose INFO level.
# https://github.com/quandyfactory/dicttoxml/issues/60
logging.getLogger('dicttoxml').setLevel(logging.WARNING)

REQUIREMENTS = ['huawei-lte-api==1.1.1']

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)

DOMAIN = 'huawei_lte'
DATA_KEY = 'huawei_lte'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(cv.ensure_list, [vol.Schema({
        vol.Required(CONF_URL): cv.url,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    })])
}, extra=vol.ALLOW_EXTRA)


@attr.s
class RouterData:
    """Class for router state."""

    client = attr.ib()
    device_information = attr.ib(init=False, factory=dict)
    device_signal = attr.ib(init=False, factory=dict)
    traffic_statistics = attr.ib(init=False, factory=dict)
    wlan_host_list = attr.ib(init=False, factory=dict)

    _subscriptions = attr.ib(init=False, factory=set)

    def __attrs_post_init__(self) -> None:
        """Fetch device information once, for serial number in @unique_ids."""
        self.subscribe("device_information")
        self._update()
        self.unsubscribe("device_information")

    def __getitem__(self, path: str):
        """
        Get value corresponding to a dotted path.

        The first path component designates a member of this class
        such as device_information, device_signal etc, and the remaining
        path points to a value in the member's data structure.
        """
        root, *rest = path.split(".")
        try:
            data = getattr(self, root)
        except AttributeError as err:
            raise KeyError from err
        return reduce(operator.getitem, rest, data)

    def subscribe(self, path: str) -> None:
        """Subscribe to given router data entries."""
        self._subscriptions.add(path.split(".")[0])

    def unsubscribe(self, path: str) -> None:
        """Unsubscribe from given router data entries."""
        self._subscriptions.discard(path.split(".")[0])

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self) -> None:
        """Call API to update data."""
        self._update()

    def _update(self) -> None:
        debugging = _LOGGER.isEnabledFor(logging.DEBUG)
        if debugging or "device_information" in self._subscriptions:
            self.device_information = self.client.device.information()
            _LOGGER.debug("device_information=%s", self.device_information)
        if debugging or "device_signal" in self._subscriptions:
            self.device_signal = self.client.device.signal()
            _LOGGER.debug("device_signal=%s", self.device_signal)
        if debugging or "traffic_statistics" in self._subscriptions:
            self.traffic_statistics = \
                self.client.monitoring.traffic_statistics()
            _LOGGER.debug("traffic_statistics=%s", self.traffic_statistics)
        if debugging or "wlan_host_list" in self._subscriptions:
            self.wlan_host_list = self.client.wlan.host_list()
            _LOGGER.debug("wlan_host_list=%s", self.wlan_host_list)


@attr.s
class HuaweiLteData:
    """Shared state."""

    data = attr.ib(init=False, factory=dict)

    def get_data(self, config):
        """Get the requested or the only data value."""
        if CONF_URL in config:
            return self.data.get(config[CONF_URL])
        if len(self.data) == 1:
            return next(iter(self.data.values()))

        return None


def setup(hass, config) -> bool:
    """Set up Huawei LTE component."""
    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = HuaweiLteData()
    for conf in config.get(DOMAIN, []):
        _setup_lte(hass, conf)
    return True


def _setup_lte(hass, lte_config) -> None:
    """Set up Huawei LTE router."""
    from huawei_lte_api.AuthorizedConnection import AuthorizedConnection
    from huawei_lte_api.Client import Client

    url = lte_config[CONF_URL]
    username = lte_config[CONF_USERNAME]
    password = lte_config[CONF_PASSWORD]

    connection = AuthorizedConnection(
        url,
        username=username,
        password=password,
    )
    client = Client(connection)

    data = RouterData(client)
    hass.data[DATA_KEY].data[url] = data

    def cleanup(event):
        """Clean up resources."""
        client.user.logout()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, cleanup)
