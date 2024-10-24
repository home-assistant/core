"""API for Viessmann ViCare bound to Home Assistant OAuth."""

from asyncio import run_coroutine_threadsafe
import logging
from typing import Any

from authlib.integrations.base_client import InvalidTokenError, TokenExpiredError
from PyViCare import Feature
from PyViCare.PyViCareAbstractOAuthManager import (
    API_BASE_URL,
    AbstractViCareOAuthManager,
)
from PyViCare.PyViCareUtils import PyViCareInternalServerError, PyViCareRateLimitError

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

_LOGGER = logging.getLogger(__name__)


class ConfigEntryAuth(AbstractViCareOAuthManager):
    """Provide Viessmann ViCare authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize Viessmann ViCare Auth."""
        self.hass = hass
        self.session = oauth_session
        super().__init__(self.session.token)

    # def refresh_tokens(self) -> str:
    def renewToken(self) -> None:
        """Refresh Viessmann ViCare tokens using Home Assistant OAuth2 session."""
        run_coroutine_threadsafe(
            self.session.async_ensure_token_valid(), self.hass.loop
        ).result()

        # return self.session.token["access_token"]

    def get(self, url: str) -> Any:
        """Perform get request."""
        try:
            run_coroutine_threadsafe(
                self.session.async_ensure_token_valid(), self.hass.loop
            ).result()
            # response = self.__oauth.get(f"{API_BASE_URL}{url}", timeout=31).json()
            client_response = run_coroutine_threadsafe(
                self.session.async_request("GET", f"{API_BASE_URL}{url}"),
                self.hass.loop,
            ).result(timeout=31)

            response = run_coroutine_threadsafe(
                client_response.json(), self.hass.loop
            ).result()
            # logger.debug(self.__oauth)
            # logger.debug("Response to get request: %s", response)
            self.__handle_expired_token(response)
            self.__handle_rate_limit(response)
            self.__handle_server_error(response)
            return response
        except TokenExpiredError:
            self.renewToken()
            return self.get(url)
        except InvalidTokenError:
            self.renewToken()
            return self.get(url)

    # def post(self, url, data) -> Any:
    #     """POST URL using OAuth session. Automatically renew the token if needed
    #     Parameters
    #     ----------
    #     url : str
    #         URL to get
    #     data : str
    #         Data to post

    #     Returns
    #     -------
    #     result: json
    #         json representation of the answer
    #     """
    #     headers = {"Content-Type": "application/json",
    #                "Accept": "application/vnd.siren+json"}
    #     try:

    #         response = run_coroutine_threadsafe(
    #             self.session.async_request("POST", f"{API_BASE_URL}{url}"), self.hass.loop
    #         ).result(timeout=31).json()
    #         response = self.__oauth.post(
    #             f"{API_BASE_URL}{url}", data, headers=headers).json()
    #         self.__handle_expired_token(response)
    #         self.__handle_rate_limit(response)
    #         self.__handle_command_error(response)
    #         return response
    #     except TokenExpiredError:
    #         self.renewToken()
    #         return self.post(url, data)
    #     except InvalidTokenError:
    #         self.renewToken()
    #         return self.get(url)

    def __handle_expired_token(self, response):
        if "error" in response and response["error"] == "EXPIRED TOKEN":
            raise TokenExpiredError(response)

    def __handle_rate_limit(self, response):
        if not Feature.raise_exception_on_rate_limit:
            return

        if "statusCode" in response and response["statusCode"] == 429:
            raise PyViCareRateLimitError(response)

    def __handle_server_error(self, response):
        if "statusCode" in response and response["statusCode"] >= 500:
            raise PyViCareInternalServerError(response)
