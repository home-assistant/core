import logging
from datetime import datetime, timedelta

import aiohttp
import homeassistant.exceptions as ha_exceptions
from bs4 import BeautifulSoup

_LOGGER = logging.getLogger(__name__)

LOGIN_PAGE_URL = "https://www.enel.it/it/login"
LOGIN_URL = "https://accounts.enel.com/samlsso"
SAMLAUTH_URL = "https://www.enel.it/bin/samlauth"
AGGREGATE_CONSUMPTION_URL = (
    "https://www.enel.it/bin/areaclienti/auth/aggregateConsumption"
)


class EnelGridSession:
    """Handles Enel portal login and authenticated session management."""

    def __init__(self, username, password, pod, user_number):
        self.username = username
        self.password = password
        self.pod = pod
        self.user_number = user_number
        self.session = None

    async def close(self):
        await self.session.close()

    async def get_session_data_key(self):
        """Fetch sessionDataKey from login page."""
        async with self.session.get(LOGIN_PAGE_URL) as response:
            response.raise_for_status()
            html = await response.text()
            soup = BeautifulSoup(html, "html.parser")
            input_tag = soup.find("input", {"name": "sessionDataKey"})

            if not input_tag:
                _LOGGER.error(
                    "sessionDataKey not found on login page, probably Enel changed their login page structure."
                )
                raise ha_exceptions.ConfigEntryAuthFailed(
                    "sessionDataKey not found on login page, probably Enel changed their login page structure."
                )

            session_data_key = input_tag.get("value")
            return session_data_key

    async def login(self):
        """Complete login process including SAMLResponse submission."""
        self.session = aiohttp.ClientSession()
        session_data_key = await self.get_session_data_key()
        saml_response = await self.submit_login_form(session_data_key)
        await self.submit_saml_response(saml_response)
        _LOGGER.info("Login and session enrichment completed.")

    async def submit_login_form(self, session_data_key):
        """Submit login form and extract SAMLResponse."""
        payload = {
            "username": self.username,
            "password": self.password,
            "sessionDataKey": session_data_key,
            "tocommonauth": "true",
        }

        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        async with self.session.post(
            LOGIN_URL, data=payload, headers=headers
        ) as response:
            response.raise_for_status()
            html = await response.text()
            soup = BeautifulSoup(html, "html.parser")
            saml_response_input = soup.find("input", {"name": "SAMLResponse"})

            if not saml_response_input:
                _LOGGER.error("Login failed: SAMLResponse not found after login")
                raise ha_exceptions.ConfigEntryAuthFailed(
                    "Enel login failed: invalid credentials or unexpected page structure."
                )
                # raise Exception("SAMLResponse not found after login")

            return saml_response_input.get("value")

    async def submit_saml_response(self, saml_response):
        """Submit SAMLResponse to enrich cookies."""
        payload = {"SAMLResponse": saml_response}
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        async with self.session.post(
            SAMLAUTH_URL, data=payload, headers=headers
        ) as response:
            response.raise_for_status()

        _LOGGER.info("Session cookies enriched after SAMLResponse submission.")

    async def fetch_consumption_data(self):
        """Fetch data after ensuring login."""
        await self.login()

        validity_from, validity_to = get_date_range()

        url = (
            f"{AGGREGATE_CONSUMPTION_URL}?pod={self.pod}&userNumber={self.user_number}"
            f"&validityFrom={validity_from}&validityTo={validity_to}"
            f"&_={int(datetime.now().timestamp() * 1000)}"
        )

        _LOGGER.info(f"URL: {url}")

        async with self.session.get(url) as response:
            response.raise_for_status()
            json = await response.json()
            await self.close()
            return json


def get_date_range():
    """Calculate validityFrom (today - 1 month) and validityTo (today) in DDMMYYYY format."""
    today = datetime.today()
    first_of_last_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)

    validity_from = first_of_last_month.strftime("%d%m%Y")
    validity_to = today.strftime("%d%m%Y")

    return validity_from, validity_to
