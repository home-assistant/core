"""Support for Vultr."""

from datetime import timedelta
import logging

import requests

_LOGGER = logging.getLogger(__name__)


ATTR_ALLOWED_BANDWIDTH = "allowed_bandwidth_gb"

ATTR_CURRENT_BANDWIDTH_IN = "current_bandwidth_gb_in"
ATTR_CURRENT_BANDWIDTH_OUT = "current_bandwidth_gb_out"
ATTR_CREATED_AT = "date_created"
ATTR_DISK = "disk"
ATTR_INSTANCE_ID = "id"
ATTR_INSTANCE_LABEL = "label"
ATTR_IPV4_ADDRESS = "main_ip"
ATTR_ACCOUNT_BALANCE = "balance"
ATTR_MEMORY = "ram"
ATTR_OS = "os"

ATTR_PENDING_CHARGES = "pending_charges"

ATTR_REGION = "region"
ATTR_VCPUS = "vcpu_count"
CONF_INSTANCE_ID = "instance"
DOMAIN = "vultr"

NOTIFICATION_ID = "vultr_notification"
NOTIFICATION_TITLE = "Vultr Setup"

DEFAULT_NAME = "Vultr {}"
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)


class Vultr:
    """Handle all communication with the Vultr API."""

    url = "https://api.vultr.com/v2"

    def __init__(self, api_key):
        """Initialize the Vultr connection."""
        self._api_key = api_key
        self.api_key = api_key
        self.s = requests.session()
        if self.api_key:
            self.s.headers.update({"Authorization": f"Bearer {self.api_key}"})

    def _get(self, url):
        r = self.s.get(url, timeout=10)
        if not r.ok:
            r.raise_for_status()
        return r.json()

    def _post(self, url, data):
        r = self.s.post(url, json=data, timeout=10)
        if not r.ok:
            r.raise_for_status()
        return r.json()

    def get_instance(self, instance_id: str):
        """Retrieve Vultr instance details."""
        url = f"{self.url}/instances/{instance_id}"
        return self._get(url)["instance"]

    def get_account_info(self):
        """Retrieve Vultr account info."""
        url = f"{self.url}/account"
        return self._get(url)["account"]

    def get_account_bandwidth_info(self):
        """Retrieve Vultr account bandwidth info."""
        url = f"{self.url}/account/bandwidth"
        return self._get(url)["bandwidth"]["currentMonthToDate"]

    def halt(self, instance_id: str):
        """Halt an instance (hard power off)."""
        data = {"instance_ids": [instance_id]}
        url = f"{self.url}/instances/halt"
        self._post(url, data)

    def start(self, instance_id: str):
        """Start an instance."""
        data = {"instance_ids": [instance_id]}
        url = f"{self.url}/instances/start"
        self._post(url, data)
