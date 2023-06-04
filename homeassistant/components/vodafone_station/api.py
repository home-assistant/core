"""Support for Vodafone Station."""
import datetime
import hashlib
import hmac
import html
import re
import urllib.parse

import requests
import urllib3

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_SSL, CONF_USERNAME
from homeassistant.helpers.typing import ConfigType

from .const import _LOGGER

# Suppress only the needed single warning from urllib3.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class VodafoneStationApi:
    """Queries router running Vodafone Station firmware."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the scanner."""
        self.host = config[CONF_HOST]
        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]
        self.protocol = "https" if config[CONF_SSL] else "http"
        self.base_url = f"{self.protocol}://{self.host}"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Fedora; Linux x86_64; rv:78.0) Gecko/20100101 Firefox/78.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.5",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/login.html",
            "DNT": "1",
        }
        self.session = requests.Session()
        self.csrf_token = ""
        self.encryption_key = ""

    def _get_csrf_token(self) -> None:
        """Load login page to get csrf token."""

        url = f"{self.base_url}/login.html"
        reply = self.session.get(
            url, headers=self.headers, timeout=10, verify=False, allow_redirects=False
        )
        tokens = re.search("(?<=csrf_token = ')[^']+", reply.text)
        if not tokens:
            return None
        self.csrf_token = tokens.group(0)
        _LOGGER.debug("csrf_token: <%s>", self.csrf_token)

    def _get_user_lang(self) -> None:
        """Load user_lang page to get."""

        timestamp = datetime.datetime.now().strftime("%s")
        url = f"{self.base_url}/data/user_lang.json?_={timestamp}&csrf_token={self.csrf_token}"
        reply = self.session.get(
            url, headers=self.headers, timeout=10, verify=False, allow_redirects=False
        )

        j = reply.json()
        user_obj = {}
        for item in j:
            key = list(item.keys())[0]
            val = list(item.values())[0]
            user_obj[key] = val

        self.encryption_key = user_obj["encryption_key"]
        _LOGGER.debug("encryption_key: <%s>", self.encryption_key)

    def _encrypt_string(self, credential: str) -> str:
        """Encrypt username or password for login."""

        credential = urllib.parse.quote(credential)
        credential = html.unescape(credential)
        hash1_str = hmac.new(
            bytes("$1$SERCOMM$", "latin-1"),
            msg=bytes(credential, "latin-1"),
            digestmod=hashlib.sha256,
        ).hexdigest()

        return hmac.new(
            bytes(self.encryption_key, "latin-1"),
            msg=bytes(hash1_str, "latin-1"),
            digestmod=hashlib.sha256,
        ).hexdigest()

    def _set_cookie(self) -> None:
        """Enable required session cookie."""
        cookie_obj = requests.cookies.create_cookie(
            domain=self.host, name="login_uid", value="1"
        )
        self.session.cookies.set_cookie(cookie_obj)

    def _reset(self) -> bool:
        """Reset page content before loading."""

        payload = {"chk_sys_busy": ""}
        timestamp = datetime.datetime.now().strftime("%s")
        url = f"{self.base_url}/data/reset.json?_={timestamp}&csrf_token={self.csrf_token}"
        reply = self.session.post(
            url,
            data=payload,
            headers=self.headers,
            timeout=10,
            verify=False,
            allow_redirects=False,
        )

        return reply.status_code == 200

    def login(self) -> bool:
        """Router login."""

        self._get_csrf_token()
        self._get_user_lang()
        self._set_cookie()
        self._reset()

        username = (
            self._encrypt_string(self.username)
            if self.protocol == "https"
            else self.username
        )
        payload = {
            "LoginName": username,
            "LoginPWD": self._encrypt_string(self.password),
        }
        timestamp = datetime.datetime.now().strftime("%s")
        url = f"{self.base_url}/data/login.json?_={timestamp}&csrf_token={self.csrf_token}"
        reply = self.session.post(
            url,
            data=payload,
            headers=self.headers,
            timeout=10,
            verify=False,
            allow_redirects=True,
        )
        if reply.status_code != 200:
            return False
        return True

    def overview(self) -> dict:
        """Load overview page data."""
        timestamp = datetime.datetime.now().strftime("%s")
        url = f"{self.base_url}/data/overview.json?_={timestamp}&csrf_token={self.csrf_token}"

        reply = self.session.get(
            url, headers=self.headers, timeout=10, verify=False, allow_redirects=False
        )
        _LOGGER.debug("Full Response: %s", reply.json())
        return reply.json()

    def logout(self) -> None:
        """Router logout."""
        self.session.cookies.clear(
            domain=self.host,
        )
