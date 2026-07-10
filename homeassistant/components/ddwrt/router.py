"""Client for querying a wireless router running DD-WRT firmware."""

from http import HTTPStatus
import logging
import re

import requests

_LOGGER = logging.getLogger(__name__)

_DDWRT_DATA_REGEX = re.compile(r"\{(\w+)::([^\}]*)\}")
_MAC_REGEX = re.compile(r"(([0-9A-Fa-f]{1,2}\:){5}[0-9A-Fa-f]{1,2})")

_HTTP_TIMEOUT = 4

type DdWrtClients = dict[str, dict[str, str | None]]


class DdWrtConnectionError(Exception):
    """Raised when the router is unreachable or rejects the credentials."""


class DdWrtRouter:
    """Query a wireless router running DD-WRT firmware over HTTP."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        *,
        use_ssl: bool,
        verify_ssl: bool,
        wireless_only: bool,
    ) -> None:
        """Initialize the DD-WRT router client."""
        self._protocol = "https" if use_ssl else "http"
        self._host = host
        self._username = username
        self._password = password
        self._verify_ssl = verify_ssl
        self._wireless_only = wireless_only

    def get_clients(self) -> DdWrtClients:
        """Return the connected clients keyed by MAC address.

        Also serves as the connectivity/credentials check: it raises
        DdWrtConnectionError when the router cannot be reached, the
        credentials are rejected, or the response is not a valid DD-WRT
        status page (for example a login or proxy page returned with a
        200 status).
        """
        lan = self._get_data("Status_Lan.live.asp")
        if self._wireless_only:
            active = self._get_data("Status_Wireless.live.asp")
            field = "active_wireless"
        else:
            active = lan
            field = "arp_table"
        if field not in active:
            raise DdWrtConnectionError(
                f"Unexpected response from DD-WRT router at {self._host}, "
                f"missing '{field}' field"
            )
        macs = self._extract_macs(active[field])
        leases = self._parse_leases(lan)
        return {mac: leases.get(mac, {"hostname": None, "ip": None}) for mac in macs}

    @staticmethod
    def _parse_leases(data: dict[str, str]) -> DdWrtClients:
        """Parse the DHCP leases from a Status_Lan response."""
        if not (raw := data.get("dhcp_leases")):
            return {}
        cleaned = raw.replace('"', "").replace("'", "").replace(" ", "")
        elements = cleaned.split(",")
        leases: DdWrtClients = {}
        for idx in range(len(elements) // 5):
            base = idx * 5
            mac = elements[base + 2]
            leases[mac] = {
                "hostname": elements[base] or None,
                "ip": elements[base + 1] or None,
            }
        return leases

    @staticmethod
    def _extract_macs(raw: str | None) -> list[str]:
        """Extract the MAC addresses from a DD-WRT list field."""
        if not raw:
            return []
        cleaned = raw.strip().strip("'")
        return [item for item in cleaned.split("','") if _MAC_REGEX.match(item)]

    def _get_data(self, path: str) -> dict[str, str]:
        """Retrieve and parse a DD-WRT live status endpoint."""
        url = f"{self._protocol}://{self._host}/{path}"
        try:
            response = requests.get(
                url,
                auth=(self._username, self._password),
                timeout=_HTTP_TIMEOUT,
                verify=self._verify_ssl,
            )
        except requests.exceptions.RequestException as err:
            raise DdWrtConnectionError(
                f"Error connecting to DD-WRT router at {self._host}"
            ) from err

        if response.status_code == HTTPStatus.UNAUTHORIZED:
            raise DdWrtConnectionError(
                "Authentication failed, check your username and password"
            )
        if response.status_code != HTTPStatus.OK:
            raise DdWrtConnectionError(
                f"Unexpected response from DD-WRT router: {response.status_code}"
            )
        return dict(_DDWRT_DATA_REGEX.findall(response.text))
