"""SamsungTV Encrypted."""
# flake8: noqa
# pylint: disable=[missing-class-docstring,missing-function-docstring]
from __future__ import annotations

import logging
import re
from typing import Any

import aiohttp

from . import crypto

LOGGER = logging.getLogger(__name__)


class SamsungTVEncryptedWSAsyncAuthenticator:
    _USER_ID = "654321"
    _APP_ID = "12345"
    _DEVICE_ID = "7e509404-9d7c-46b4-8f6a-e2a9668ad184"

    def __init__(
        self,
        host: str,
        *,
        web_session: aiohttp.ClientSession,
        port: int = 8000,
        timeout: float | None = None,
    ) -> None:
        self._host = host
        self._web_session = web_session
        self._port = port
        self._timeout = timeout
        self._sk_prime: Any | None = None

    def _get_full_url(self, route: str) -> str:
        return f"http://{self._host}:{self._port}/{route}"

    def _get_full_request_url(self, step: int) -> str:
        return self._get_full_url(
            f"ws/pairing?step={step}&app_id={self._APP_ID}&device_id={self._DEVICE_ID}"
        )

    async def _show_pin_page_on_tv(self) -> None:
        url = self._get_full_url("ws/apps/CloudPINPage")
        LOGGER.debug("Tx: POST %s", url)
        async with self._web_session.post(url, data="pin4") as response:
            LOGGER.debug("Rx: %s", await response.text())

    async def _check_pin_page_on_tv(self) -> bool:
        url = self._get_full_url("ws/apps/CloudPINPage")
        LOGGER.debug("Tx: GET %s", url)
        async with self._web_session.get(url) as response:
            LOGGER.debug("Rx: %s", await response.text())
            page = await response.text()
        output = re.search("state>([^<>]*)</state>", page, flags=re.IGNORECASE)
        if output is not None:
            state = output.group(1)
            LOGGER.info("Current PIN state: %s", state)
            if state == "stopped":
                return False
        return True

    async def start_pairing(self) -> None:
        if await self._check_pin_page_on_tv():
            LOGGER.info("Pin ON TV")
        else:
            LOGGER.info("Pin NOT on TV")
            await self._show_pin_page_on_tv()

    async def _first_step_of_pairing(self) -> None:
        url = self._get_full_request_url(0) + "&type=1"
        LOGGER.debug("Tx: GET %s", url)
        async with self._web_session.get(url) as response:
            LOGGER.debug("Rx: %s", await response.text())

    async def _second_step_of_pairing(self, pin: str) -> dict[str, Any] | None:
        hello_output = crypto.generateServerHello(
            self._USER_ID, pin
        )  # type: ignore[no-untyped-call]
        if not hello_output:
            return None
        content = (
            '{"auth_Data":{"auth_type":"SPC","GeneratorServerHello":"'
            + hello_output["serverHello"].hex().upper()
            + '"}}'
        )
        url = self._get_full_request_url(1)
        LOGGER.debug("Tx: POST %s", url)
        async with self._web_session.post(url, data=content) as response:
            LOGGER.debug("Rx: %s", await response.text())
            response_text = await response.text()
        output = re.search(
            r"request_id.*?(\d).*?GeneratorClientHello.*?:.*?(\d[0-9a-zA-Z]*)",
            response_text,
            flags=re.IGNORECASE,
        )
        if output is None:
            return None
        # request_id = output.group(1)
        client_hello = output.group(2)
        # lastRequestId = int(requestId)
        return crypto.parseClientHello(  # type: ignore[no-untyped-call,no-any-return]
            client_hello, hello_output["hash"], hello_output["AES_key"], self._USER_ID
        )

    async def try_pin(self, pin: str) -> str | None:
        LOGGER.debug("Trying pin: '%s'", pin)
        await self._first_step_of_pairing()
        result = await self._second_step_of_pairing(pin)
        if result:
            LOGGER.info("Pin accepted :)")
            token = result["ctx"].hex()
            self._sk_prime = result["SKPrime"]
            LOGGER.info("Token (ctx): %s", token)
            return token  # type: ignore[no-any-return]

        LOGGER.info("Pin incorrect. Please try again")
        return None

    async def _acknowledge_exchange(self) -> str:
        server_ack_message = crypto.generateServerAcknowledge(self._sk_prime)  # type: ignore[no-untyped-call]
        content = (
            '{"auth_Data":{"auth_type":"SPC","request_id":"0","ServerAckMsg":"'
            + server_ack_message
            + '"}}'
        )
        url = self._get_full_request_url(2)
        LOGGER.debug("Tx: POST %s", url)
        async with self._web_session.post(url, data=content) as response:
            LOGGER.debug("Rx: %s", await response.text())
            response_text = await response.text()
        if "secure-mode" in response_text:
            raise Exception("TODO: Implement handling of encryption flag!!!!")
        output = re.search(
            r"ClientAckMsg.*?:.*?(\d[0-9a-zA-Z]*).*?session_id.*?(\d)",
            response_text,
            flags=re.IGNORECASE,
        )
        if output is None:
            raise Exception("Unable to get session_id and/or ClientAckMsg!!!")
        client_ack = output.group(1)
        if not crypto.parseClientAcknowledge(client_ack, self._sk_prime):  # type: ignore[no-untyped-call]
            raise Exception("Parse client ac message failed.")

        session_id = output.group(2)
        LOGGER.info("Got sessionId: %s", session_id)
        return session_id

    async def _close_pin_page_on_tv(self) -> None:
        url = self._get_full_url("ws/apps/CloudPINPage/run")
        LOGGER.debug("Tx: DELETE %s", url)
        async with self._web_session.delete(url) as response:
            LOGGER.debug("Rx: %s", await response.text())

    async def get_session_id_and_close(self) -> str:
        session_id = await self._acknowledge_exchange()
        LOGGER.info("SessionID: %s", session_id)
        await self._close_pin_page_on_tv()
        LOGGER.info("Authorization successful :)\n")
        return session_id


async def get_token(
    host: str, web_session: aiohttp.ClientSession, port: int = 8000
) -> tuple[str, str] | None:
    authenticator = SamsungTVEncryptedWSAsyncAuthenticator(
        host, web_session=web_session, port=port
    )
    await authenticator.start_pairing()
    token: str | None = None
    while not token:
        pin = input("Please enter pin from tv: ")
        token = await authenticator.try_pin(pin)

    session_id = await authenticator.get_session_id_and_close()

    return (token, session_id)
