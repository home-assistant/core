"""Code to communicate with the cloud API."""
import logging
from urllib.parse import urljoin

import requests

from . import auth_api
from .const import REQUEST_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class CloudApi:
    """Interact with the cloud API."""

    def __init__(self, cloud):
        """Initialize the cloud API."""
        self.cloud = cloud

    def make_api_call(self, path, method='POST'):
        """Make a call to the Cloud API."""
        auth_api.check_token(self.cloud)

        uri = urljoin(self.cloud.api_base, path)
        response = requests.request(
            method, uri, timeout=REQUEST_TIMEOUT,
            headers={"Authorization": self.cloud.id_token})

        return response

    def retrieve_iot_certificate(self):
        """Retrieve the certificate to connect to IoT."""
        resp = self.make_api_call('device/create')
        resp.raise_for_status()
        return resp.json()
