"""Support for Huawei LTE routers."""

from datetime import timedelta
from functools import reduce
from urllib.parse import urlparse
import ipaddress
import logging
import operator
from typing import Any, Callable

import voluptuous as vol
import attr
from getmac import get_mac_address
from huawei_lte_api.AuthorizedConnection import AuthorizedConnection
from huawei_lte_api.Client import Client
from huawei_lte_api.exceptions import ResponseErrorNotSupportedException

from homeassistant.const import (
    CONF_URL,
    CONF_USERNAME,
    CONF_PASSWORD,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.util import Throttle
from .const import (
    DOMAIN,
    KEY_DEVICE_INFORMATION,
    KEY_DEVICE_SIGNAL,
    KEY_MONITORING_TRAFFIC_STATISTICS,
    KEY_WLAN_HOST_LIST,
)


_LOGGER = logging.getLogger(__name__)

# dicttoxml (used by huawei-lte-api) has uselessly verbose INFO level.
# https://github.com/quandyfactory/dicttoxml/issues/60
logging.getLogger("dicttoxml").setLevel(logging.WARNING)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_URL): cv.url,
                        vol.Required(CONF_USERNAME): cv.string,
                        vol.Required(CONF_PASSWORD): cv.string,
                    }
                )
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)


@attr.s
class RouterData:
    """Class for router state."""

    client = attr.ib()
    mac = attr.ib()
    device_information = attr.ib(init=False, factory=dict)
    device_signal = attr.ib(init=False, factory=dict)
    monitoring_traffic_statistics = attr.ib(init=False, factory=dict)
    wlan_host_list = attr.ib(init=False, factory=dict)

    _subscriptions = attr.ib(init=False, factory=set)

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

        def get_data(path: str, func: Callable[[None], Any]) -> None:
            if debugging or path in self._subscriptions:
                try:
                    setattr(self, path, func())
                except ResponseErrorNotSupportedException:
                    _LOGGER.warning("%s not supported by device", path)
                    self._subscriptions.discard(path)
                finally:
                    _LOGGER.debug("%s=%s", path, getattr(self, path))

        get_data(KEY_DEVICE_INFORMATION, self.client.device.information)
        get_data(KEY_DEVICE_SIGNAL, self.client.device.signal)
        get_data(
            KEY_MONITORING_TRAFFIC_STATISTICS, self.client.monitoring.traffic_statistics
        )
        get_data(KEY_WLAN_HOST_LIST, self.client.wlan.host_list)


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
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = HuaweiLteData()
    for conf in config.get(DOMAIN, []):
        _setup_lte(hass, conf)
    return True


def _setup_lte(hass, lte_config) -> None:
    """Set up Huawei LTE router."""
    url = lte_config[CONF_URL]
    username = lte_config[CONF_USERNAME]
    password = lte_config[CONF_PASSWORD]

    # Get MAC address for use in unique ids. Being able to use something
    # from the API would be nice, but all of that seems to be available only
    # through authenticated calls (e.g. device_information.SerialNumber), and
    # we want this available and the same when unauthenticated too.
    host = urlparse(url).hostname
    try:
        if ipaddress.ip_address(host).version == 6:
            mode = "ip6"
        else:
            mode = "ip"
    except ValueError:
        mode = "hostname"
    mac = get_mac_address(**{mode: host})

    connection = AuthorizedConnection(url, username=username, password=password)
    client = Client(connection)

    data = RouterData(client, mac)
    hass.data[DOMAIN].data[url] = data

    def cleanup(event):
        """Clean up resources."""
        try:
            client.user.logout()
        except ResponseErrorNotSupportedException as ex:
            _LOGGER.debug("Logout not supported by device", exc_info=ex)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, cleanup)
