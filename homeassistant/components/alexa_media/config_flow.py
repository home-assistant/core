"""
Alexa Config Flow.

SPDX-License-Identifier: Apache-2.0

For more details about this platform, please refer to the documentation at
https://community.home-assistant.io/t/echo-devices-alexa-as-media-player-testers-needed/58639
"""
from asyncio import sleep
from collections import OrderedDict
import datetime
from datetime import timedelta
from functools import reduce
import logging
import re
from typing import Any, Dict, List, Optional, Text

from aiohttp import ClientConnectionError, ClientSession, web, web_response
from aiohttp.web_exceptions import HTTPBadRequest
from alexapy import (
    AlexaLogin,
    AlexaProxy,
    AlexapyConnectionError,
    AlexapyPyotpInvalidKey,
    __version__ as alexapy_version,
    hide_email,
    obfuscate,
)
from homeassistant import config_entries
from homeassistant.components.http.view import HomeAssistantView
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_URL
from homeassistant.core import callback
from homeassistant.data_entry_flow import UnknownFlow
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.util import slugify
import voluptuous as vol
from yarl import URL

from .const import (
    AUTH_CALLBACK_NAME,
    AUTH_CALLBACK_PATH,
    AUTH_PROXY_NAME,
    AUTH_PROXY_PATH,
    CONF_COOKIES_TXT,
    CONF_DEBUG,
    CONF_EXCLUDE_DEVICES,
    CONF_EXTENDED_ENTITY_DISCOVERY,
    CONF_HASS_URL,
    CONF_INCLUDE_DEVICES,
    CONF_OAUTH,
    CONF_OAUTH_LOGIN,
    CONF_OTPSECRET,
    CONF_PROXY,
    CONF_QUEUE_DELAY,
    CONF_SECURITYCODE,
    CONF_TOTP_REGISTER,
    DATA_ALEXAMEDIA,
    DEFAULT_EXTENDED_ENTITY_DISCOVERY,
    DEFAULT_QUEUE_DELAY,
    DOMAIN,
    HTTP_COOKIE_HEADER,
    STARTUP,
)
from .helpers import calculate_uuid

_LOGGER = logging.getLogger(__name__)


@callback
def configured_instances(hass):
    """Return a set of configured Alexa Media instances."""
    return {entry.title for entry in hass.config_entries.async_entries(DOMAIN)}


@callback
def in_progess_instances(hass):
    """Return a set of in progress Alexa Media flows."""
    return {entry["flow_id"] for entry in hass.config_entries.flow.async_progress()}


@config_entries.HANDLERS.register(DOMAIN)
class AlexaMediaFlowHandler(config_entries.ConfigFlow):
    """Handle a Alexa Media config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL
    proxy: AlexaProxy = None
    proxy_view: "AlexaMediaAuthorizationProxyView" = None

    def _update_ord_dict(self, old_dict: OrderedDict, new_dict: dict) -> OrderedDict:
        result: OrderedDict = OrderedDict()
        for k, v in old_dict.items():
            for key, value in new_dict.items():
                if k == key:
                    result.update([(key, value)])
                    break
            if k not in result:
                result.update([(k, v)])
        return result

    def __init__(self):
        """Initialize the config flow."""
        if self.hass and not self.hass.data.get(DATA_ALEXAMEDIA):
            _LOGGER.info(STARTUP)
            _LOGGER.info("Loaded alexapy==%s", alexapy_version)
        self.login = None
        self.securitycode: Optional[Text] = None
        self.automatic_steps: int = 0
        self.config = OrderedDict()
        self.proxy_schema = None
        self.data_schema = OrderedDict(
            [
                (vol.Optional(CONF_PROXY, default=False), bool),
                (vol.Required(CONF_EMAIL), str),
                (vol.Required(CONF_PASSWORD), str),
                (vol.Required(CONF_URL, default="amazon.com"), str),
                (vol.Optional(CONF_SECURITYCODE), str),
                (vol.Optional(CONF_OTPSECRET), str),
                (vol.Optional(CONF_DEBUG, default=False), bool),
                (vol.Optional(CONF_INCLUDE_DEVICES, default=""), str),
                (vol.Optional(CONF_EXCLUDE_DEVICES, default=""), str),
                (vol.Optional(CONF_SCAN_INTERVAL, default=60), int),
                (vol.Optional(CONF_COOKIES_TXT, default=""), str),
                (vol.Optional(CONF_OAUTH_LOGIN, default=True), bool),
            ]
        )
        self.captcha_schema = OrderedDict(
            [
                (vol.Optional(CONF_PROXY, default=False), bool),
                (vol.Required(CONF_PASSWORD), str),
                (
                    vol.Optional(
                        CONF_SECURITYCODE,
                        default=self.securitycode if self.securitycode else "",
                    ),
                    str,
                ),
                (vol.Required("captcha"), str),
            ]
        )
        self.twofactor_schema = OrderedDict(
            [
                (vol.Optional(CONF_PROXY, default=False), bool),
                (
                    vol.Required(
                        CONF_SECURITYCODE,
                        default=self.securitycode if self.securitycode else "",
                    ),
                    str,
                ),
            ]
        )
        self.claimspicker_schema = OrderedDict(
            [
                (vol.Optional(CONF_PROXY, default=False), bool),
                (
                    vol.Required("claimsoption", default=0),
                    vol.All(cv.positive_int, vol.Clamp(min=0)),
                ),
            ]
        )
        self.authselect_schema = OrderedDict(
            [
                (vol.Optional(CONF_PROXY, default=False), bool),
                (
                    vol.Required("authselectoption", default=0),
                    vol.All(cv.positive_int, vol.Clamp(min=0)),
                ),
            ]
        )
        self.verificationcode_schema = OrderedDict(
            [
                (vol.Optional(CONF_PROXY, default=False), bool),
                (vol.Required("verificationcode"), str),
            ]
        )
        self.totp_register = OrderedDict(
            [(vol.Optional(CONF_TOTP_REGISTER, default=False), bool)]
        )

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user_legacy(import_config)

    async def async_step_user(self, user_input=None):
        """Provide a proxy for login."""
        self._save_user_input_to_config(user_input=user_input)
        try:
            hass_url: Text = get_url(self.hass, prefer_external=True)
        except NoURLAvailableError:
            hass_url = ""
        self.proxy_schema = OrderedDict(
            [
                (
                    vol.Required(CONF_EMAIL, default=self.config.get(CONF_EMAIL, "")),
                    str,
                ),
                (
                    vol.Required(
                        CONF_PASSWORD, default=self.config.get(CONF_PASSWORD, "")
                    ),
                    str,
                ),
                (
                    vol.Required(
                        CONF_URL, default=self.config.get(CONF_URL, "amazon.com")
                    ),
                    str,
                ),
                (
                    vol.Required(
                        CONF_HASS_URL,
                        default=self.config.get(CONF_HASS_URL, hass_url),
                    ),
                    str,
                ),
                (
                    vol.Optional(
                        CONF_OTPSECRET, default=self.config.get(CONF_OTPSECRET, "")
                    ),
                    str,
                ),
                (
                    vol.Optional(
                        CONF_DEBUG, default=self.config.get(CONF_DEBUG, False)
                    ),
                    bool,
                ),
                (
                    vol.Optional(
                        CONF_INCLUDE_DEVICES,
                        default=self.config.get(CONF_INCLUDE_DEVICES, ""),
                    ),
                    str,
                ),
                (
                    vol.Optional(
                        CONF_EXCLUDE_DEVICES,
                        default=self.config.get(CONF_EXCLUDE_DEVICES, ""),
                    ),
                    str,
                ),
                (
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=self.config.get(CONF_SCAN_INTERVAL, 60),
                    ),
                    int,
                ),
                (
                    vol.Optional(CONF_PROXY, default=self.config.get(CONF_PROXY, True)),
                    bool,
                ),
                (
                    vol.Optional(
                        CONF_OAUTH_LOGIN,
                        default=self.config.get(CONF_OAUTH_LOGIN, True),
                    ),
                    bool,
                ),
            ]
        )
        if not user_input:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(self.proxy_schema),
                description_placeholders={"message": ""},
            )
        if user_input and not user_input.get(CONF_PROXY):
            return self.async_show_form(
                step_id="user_legacy",
                data_schema=vol.Schema(self._update_schema_defaults()),
                description_placeholders={"message": ""},
            )
        if self.login is None:
            try:
                self.login = self.hass.data[DATA_ALEXAMEDIA]["accounts"][
                    self.config[CONF_EMAIL]
                ].get("login_obj")
            except KeyError:
                self.login = None
        try:
            if not self.login or self.login.session.closed:
                _LOGGER.debug("Creating new login")
                uuid_dict = await calculate_uuid(
                    self.hass, self.config.get(CONF_EMAIL), self.config[CONF_URL]
                )
                uuid = uuid_dict["uuid"]
                self.login = AlexaLogin(
                    url=self.config[CONF_URL],
                    email=self.config.get(CONF_EMAIL, ""),
                    password=self.config.get(CONF_PASSWORD, ""),
                    outputpath=self.hass.config.path,
                    debug=self.config[CONF_DEBUG],
                    otp_secret=self.config.get(CONF_OTPSECRET, ""),
                    uuid=uuid,
                    oauth_login=self.config.get(CONF_OAUTH_LOGIN, True),
                )
            else:
                _LOGGER.debug("Using existing login")
                if self.config.get(CONF_EMAIL):
                    self.login.email = self.config.get(CONF_EMAIL)
                if self.config.get(CONF_PASSWORD):
                    self.login.password = self.config.get(CONF_PASSWORD)
                if self.config.get(CONF_OTPSECRET):
                    self.login.set_totp(self.config.get(CONF_OTPSECRET, ""))
        except AlexapyPyotpInvalidKey:
            return self.async_show_form(
                step_id="user",
                errors={"base": "2fa_key_invalid"},
                description_placeholders={"message": ""},
            )
        hass_url: Text = user_input.get(CONF_HASS_URL)
        hass_url_valid: bool = False
        async with ClientSession() as session:
            try:
                async with session.get(hass_url) as resp:
                    hass_url_valid = resp.status == 200
            except ClientConnectionError:
                hass_url_valid = False
        if not hass_url_valid:
            _LOGGER.debug(
                "Unable to connect to provided Home Assistant url: %s", hass_url
            )
            return self.async_show_form(
                step_id="user",
                errors={"base": "hass_url_invalid"},
                description_placeholders={"message": ""},
            )
        if not self.proxy:
            self.proxy = AlexaProxy(
                self.login, str(URL(hass_url).with_path(AUTH_PROXY_PATH))
            )
        # Swap the login object
        self.proxy.change_login(self.login)
        if (
            user_input
            and user_input.get(CONF_OTPSECRET)
            and user_input.get(CONF_OTPSECRET).replace(" ", "")
        ):
            otp: Text = self.login.get_totp_token()
            if otp:
                _LOGGER.debug("Generating OTP from %s", otp)
                return self.async_show_form(
                    step_id="totp_register",
                    data_schema=vol.Schema(self.totp_register),
                    errors={},
                    description_placeholders={
                        "email": self.login.email,
                        "url": self.login.url,
                        "message": otp,
                    },
                )
        return await self.async_step_start_proxy(user_input)

    async def async_step_start_proxy(self, user_input=None):
        """Start proxy for login."""
        _LOGGER.debug(
            "Starting proxy for %s - %s",
            hide_email(self.login.email),
            self.login.url,
        )
        if not self.proxy_view:
            self.proxy_view = AlexaMediaAuthorizationProxyView(self.proxy.all_handler)
        else:
            _LOGGER.debug("Found existing proxy_view")
            self.proxy_view.handler = self.proxy.all_handler
        self.hass.http.register_view(AlexaMediaAuthorizationCallbackView())
        self.hass.http.register_view(self.proxy_view)
        callback_url = (
            URL(self.config["hass_url"])
            .with_path(AUTH_CALLBACK_PATH)
            .with_query({"flow_id": self.flow_id})
        )

        proxy_url = self.proxy.access_url().with_query(
            {"config_flow_id": self.flow_id, "callback_url": str(callback_url)}
        )
        if self.login.lastreq:
            self.proxy.last_resp = self.login.lastreq
            self.proxy.session.cookie_jar.update_cookies(
                self.login._session.cookie_jar.filter_cookies(
                    self.proxy._host_url.with_path("/")
                )
            )
            proxy_url = (
                self.proxy.access_url().with_path(AUTH_PROXY_PATH) / "resume"
            ).with_query(
                {"config_flow_id": self.flow_id, "callback_url": str(callback_url)}
            )
        return self.async_external_step(step_id="check_proxy", url=str(proxy_url))

    async def async_step_check_proxy(self, user_input=None):
        """Check status of proxy for login."""
        _LOGGER.debug(
            "Checking proxy response for %s - %s",
            hide_email(self.login.email),
            self.login.url,
        )
        self.proxy_view.reset()
        return self.async_external_step_done(next_step_id="finish_proxy")

    async def async_step_finish_proxy(self, user_input=None):
        """Finish auth."""
        if await self.login.test_loggedin():
            await self.login.finalize_login()
            self.config[CONF_EMAIL] = self.login.email
            self.config[CONF_PASSWORD] = self.login.password
            return await self._test_login()
        return self.async_abort(reason="login_failed")

    async def async_step_user_legacy(self, user_input=None):
        """Handle legacy input for the config flow."""
        # pylint: disable=too-many-return-statements
        self._save_user_input_to_config(user_input=user_input)
        self.data_schema = self._update_schema_defaults()
        if not user_input:
            self.automatic_steps = 0
            return self.async_show_form(
                step_id="user_legacy",
                data_schema=vol.Schema(self.data_schema),
                description_placeholders={"message": ""},
            )
        if (
            not self.config.get("reauth")
            and f"{self.config[CONF_EMAIL]} - {self.config[CONF_URL]}"
            in configured_instances(self.hass)
            and not self.hass.data[DATA_ALEXAMEDIA]["config_flows"].get(
                f"{self.config[CONF_EMAIL]} - {self.config[CONF_URL]}"
            )
        ):
            _LOGGER.debug("Existing account found")
            self.automatic_steps = 0
            return self.async_show_form(
                step_id="user_legacy",
                data_schema=vol.Schema(self.data_schema),
                errors={CONF_EMAIL: "identifier_exists"},
                description_placeholders={"message": ""},
            )
        if user_input and user_input.get(CONF_PROXY):
            return await self.async_step_user(user_input=None)
        if self.login is None:
            try:
                self.login = self.hass.data[DATA_ALEXAMEDIA]["accounts"][
                    self.config[CONF_EMAIL]
                ].get("login_obj")
            except KeyError:
                self.login = None
        try:
            if not self.login or self.login.session.closed:
                _LOGGER.debug("Creating new login")
                uuid_dict = await calculate_uuid(
                    self.hass, self.config.get(CONF_EMAIL), self.config[CONF_URL]
                )
                uuid = uuid_dict["uuid"]
                self.login = AlexaLogin(
                    url=self.config[CONF_URL],
                    email=self.config[CONF_EMAIL],
                    password=self.config[CONF_PASSWORD],
                    outputpath=self.hass.config.path,
                    debug=self.config[CONF_DEBUG],
                    otp_secret=self.config.get(CONF_OTPSECRET, ""),
                    uuid=uuid,
                    oauth_login=self.config.get(CONF_OAUTH_LOGIN, True),
                )
            else:
                _LOGGER.debug("Using existing login")
            if (
                not self.config.get("reauth")
                and user_input
                and user_input.get(CONF_OTPSECRET)
                and user_input.get(CONF_OTPSECRET).replace(" ", "")
            ):
                otp: Text = self.login.get_totp_token()
                if otp:
                    _LOGGER.debug("Generating OTP from %s", otp)
                    return self.async_show_form(
                        step_id="totp_register",
                        data_schema=vol.Schema(self.totp_register),
                        errors={},
                        description_placeholders={
                            "email": self.login.email,
                            "url": self.login.url,
                            "message": otp,
                        },
                    )
                return self.async_show_form(
                    step_id="user_legacy",
                    errors={"base": "2fa_key_invalid"},
                    description_placeholders={"message": ""},
                )
            if self.login.status:
                _LOGGER.debug("Resuming existing flow")
                return await self._test_login()
            _LOGGER.debug("Trying to login %s", self.login.status)
            await self.login.login(
                cookies=await self.login.load_cookie(
                    cookies_txt=self.config.get(CONF_COOKIES_TXT, "")
                ),
                data=self.config,
            )
            return await self._test_login()
        except AlexapyConnectionError:
            self.automatic_steps = 0
            return self.async_show_form(
                step_id="user_legacy",
                errors={"base": "connection_error"},
                description_placeholders={"message": ""},
            )
        except AlexapyPyotpInvalidKey:
            self.automatic_steps = 0
            return self.async_show_form(
                step_id="user_legacy",
                errors={"base": "2fa_key_invalid"},
                description_placeholders={"message": ""},
            )
        except BaseException as ex:  # pylyint: disable=broad-except
            _LOGGER.warning("Unknown error: %s", ex)
            if self.config[CONF_DEBUG]:
                raise
            self.automatic_steps = 0
            return self.async_show_form(
                step_id="user_legacy",
                errors={"base": "unknown_error"},
                description_placeholders={"message": ""},
            )

    async def async_step_captcha(self, user_input=None):
        """Handle the input processing of the config flow."""
        return await self.async_step_process("captcha", user_input)

    async def async_step_twofactor(self, user_input=None):
        """Handle the input processing of the config flow."""
        return await self.async_step_process("two_factor", user_input)

    async def async_step_totp_register(self, user_input=None):
        """Handle the input processing of the config flow."""
        self._save_user_input_to_config(user_input=user_input)
        if user_input and user_input.get("registered") is False:
            _LOGGER.debug("Not registered, regenerating")
            otp: Text = self.login.get_totp_token()
            if otp:
                _LOGGER.debug("Generating OTP from %s", otp)
                return self.async_show_form(
                    step_id="totp_register",
                    data_schema=vol.Schema(self.totp_register),
                    errors={},
                    description_placeholders={
                        "email": self.login.email,
                        "url": self.login.url,
                        "message": otp,
                    },
                )
        if self.proxy:
            return await self.async_step_start_proxy(user_input)
        return await self.async_step_process("totp_register", self.config)

    async def async_step_claimspicker(self, user_input=None):
        """Handle the input processing of the config flow."""
        return await self.async_step_process("claimspicker", user_input)

    async def async_step_authselect(self, user_input=None):
        """Handle the input processing of the config flow."""
        return await self.async_step_process("authselect", user_input)

    async def async_step_verificationcode(self, user_input=None):
        """Handle the input processing of the config flow."""
        return await self.async_step_process("verificationcode", user_input)

    async def async_step_action_required(self, user_input=None):
        """Handle the input processing of the config flow."""
        return await self.async_step_process("action_required", user_input)

    async def async_step_process(self, step_id, user_input=None):
        """Handle the input processing of the config flow."""
        _LOGGER.debug(
            "Processing input for %s: %s",
            step_id,
            obfuscate(user_input),
        )
        self._save_user_input_to_config(user_input=user_input)
        if user_input and user_input.get(CONF_PROXY):
            return await self.async_step_user(user_input=None)
        if user_input:
            try:
                await self.login.login(data=user_input)
            except AlexapyConnectionError:
                self.automatic_steps = 0
                return self.async_show_form(
                    step_id=step_id,
                    errors={"base": "connection_error"},
                    description_placeholders={"message": ""},
                )
            except BaseException as ex:  # pylint: disable=broad-except
                _LOGGER.warning("Unknown error: %s", ex)
                if self.config[CONF_DEBUG]:
                    raise
                self.automatic_steps = 0
                return self.async_show_form(
                    step_id=step_id,
                    errors={"base": "unknown_error"},
                    description_placeholders={"message": ""},
                )
        return await self._test_login()

    async def async_step_reauth(self, user_input=None):
        """Handle reauth processing for the config flow."""
        self._save_user_input_to_config(user_input)
        self.config["reauth"] = True
        reauth_schema = self._update_schema_defaults()
        _LOGGER.debug(
            "Creating reauth form with %s",
            obfuscate(self.config),
        )
        self.automatic_steps = 0
        if self.login is None:
            try:
                self.login = self.hass.data[DATA_ALEXAMEDIA]["accounts"][
                    self.config[CONF_EMAIL]
                ].get("login_obj")
            except KeyError:
                self.login = None
        seconds_since_login: int = (
            (datetime.datetime.now() - self.login.stats["login_timestamp"]).seconds
            if self.login
            else 60
        )
        if seconds_since_login < 60:
            _LOGGER.debug(
                "Relogin requested within %s seconds; manual login required",
                seconds_since_login,
            )
            return self.async_show_form(
                step_id="user_legacy",
                data_schema=vol.Schema(reauth_schema),
                description_placeholders={"message": "REAUTH"},
            )
        _LOGGER.debug("Attempting automatic relogin")
        await sleep(15)
        return await self.async_step_user_legacy(self.config)

    async def _test_login(self):
        # pylint: disable=too-many-statements, too-many-return-statements
        login = self.login
        email = login.email
        _LOGGER.debug("Testing login status: %s", login.status)
        if login.status and login.status.get("login_successful"):
            existing_entry = await self.async_set_unique_id(f"{email} - {login.url}")
            if self.config.get("reauth"):
                self.config.pop("reauth")
            if self.config.get(CONF_SECURITYCODE):
                self.config.pop(CONF_SECURITYCODE)
            if self.config.get(CONF_PROXY):
                self.config.pop(CONF_PROXY)
            if self.config.get("hass_url"):
                self.config.pop("hass_url")
            self.config[CONF_OAUTH] = {
                "access_token": login.access_token,
                "refresh_token": login.refresh_token,
                "expires_in": login.expires_in,
            }
            self.hass.data.setdefault(
                DATA_ALEXAMEDIA,
                {"accounts": {}, "config_flows": {}},
            )
            if existing_entry:
                self.hass.config_entries.async_update_entry(
                    existing_entry, data=self.config
                )
                _LOGGER.debug("Reauth successful for %s", hide_email(email))
                self.hass.bus.async_fire(
                    "alexa_media_relogin_success",
                    event_data={"email": hide_email(email), "url": login.url},
                )
                self.hass.components.persistent_notification.async_dismiss(
                    f"alexa_media_{slugify(email)}{slugify(login.url[7:])}"
                )
                self.hass.data[DATA_ALEXAMEDIA]["accounts"][self.config[CONF_EMAIL]][
                    "login_obj"
                ] = self.login
                self.hass.data[DATA_ALEXAMEDIA]["config_flows"][
                    f"{email} - {login.url}"
                ] = None
                return self.async_abort(reason="reauth_successful")
            _LOGGER.debug(
                "Setting up Alexa devices with %s", dict(obfuscate(self.config))
            )
            self._abort_if_unique_id_configured(self.config)
            return self.async_create_entry(
                title=f"{login.email} - {login.url}", data=self.config
            )
        if login.status and login.status.get("captcha_required"):
            new_schema = self._update_ord_dict(
                self.captcha_schema,
                {
                    vol.Required(
                        CONF_PASSWORD, default=self.config[CONF_PASSWORD]
                    ): str,
                    vol.Optional(
                        CONF_SECURITYCODE,
                        default=self.securitycode if self.securitycode else "",
                    ): str,
                },
            )
            _LOGGER.debug("Creating config_flow to request captcha")
            self.automatic_steps = 0
            return self.async_show_form(
                step_id="captcha",
                data_schema=vol.Schema(new_schema),
                errors={},
                description_placeholders={
                    "email": login.email,
                    "url": login.url,
                    "captcha_image": "[![captcha]({0})]({0})".format(
                        login.status["captcha_image_url"]
                    ),
                    "message": f"  \n> {login.status.get('error_message','')}",
                },
            )
        if login.status and login.status.get("securitycode_required"):
            _LOGGER.debug(
                "Creating config_flow to request 2FA. Saved security code %s",
                self.securitycode,
            )
            generated_securitycode: Text = login.get_totp_token()
            if (
                self.securitycode or generated_securitycode
            ) and self.automatic_steps < 2:
                if self.securitycode:
                    _LOGGER.debug(
                        "Automatically submitting securitycode %s", self.securitycode
                    )
                else:
                    _LOGGER.debug(
                        "Automatically submitting generated securitycode %s",
                        generated_securitycode,
                    )
                self.automatic_steps += 1
                await sleep(5)
                if generated_securitycode:
                    return await self.async_step_twofactor(
                        user_input={CONF_SECURITYCODE: generated_securitycode}
                    )
                return await self.async_step_twofactor(
                    user_input={CONF_SECURITYCODE: self.securitycode}
                )
            self.twofactor_schema = OrderedDict(
                [
                    (vol.Optional(CONF_PROXY, default=False), bool),
                    (
                        vol.Required(
                            CONF_SECURITYCODE,
                            default=self.securitycode if self.securitycode else "",
                        ),
                        str,
                    ),
                ]
            )
            self.automatic_steps = 0
            return self.async_show_form(
                step_id="twofactor",
                data_schema=vol.Schema(self.twofactor_schema),
                errors={},
                description_placeholders={
                    "email": login.email,
                    "url": login.url,
                    "message": f"  \n> {login.status.get('error_message','')}",
                },
            )
        if login.status and login.status.get("claimspicker_required"):
            error_message = f"  \n> {login.status.get('error_message', '')}"
            _LOGGER.debug("Creating config_flow to select verification method")
            claimspicker_message = login.status["claimspicker_message"]
            self.automatic_steps = 0
            return self.async_show_form(
                step_id="claimspicker",
                data_schema=vol.Schema(self.claimspicker_schema),
                errors={},
                description_placeholders={
                    "email": login.email,
                    "url": login.url,
                    "message": "  \n> {}  \n> {}".format(
                        claimspicker_message, error_message
                    ),
                },
            )
        if login.status and login.status.get("authselect_required"):
            _LOGGER.debug("Creating config_flow to select OTA method")
            error_message = login.status.get("error_message", "")
            authselect_message = login.status["authselect_message"]
            self.automatic_steps = 0
            return self.async_show_form(
                step_id="authselect",
                data_schema=vol.Schema(self.authselect_schema),
                description_placeholders={
                    "email": login.email,
                    "url": login.url,
                    "message": "  \n> {}  \n> {}".format(
                        authselect_message, error_message
                    ),
                },
            )
        if login.status and login.status.get("verificationcode_required"):
            _LOGGER.debug("Creating config_flow to enter verification code")
            self.automatic_steps = 0
            return self.async_show_form(
                step_id="verificationcode",
                data_schema=vol.Schema(self.verificationcode_schema),
            )
        if (
            login.status
            and login.status.get("force_get")
            and not login.status.get("ap_error_href")
        ):
            _LOGGER.debug("Creating config_flow to wait for user action")
            self.automatic_steps = 0
            return self.async_show_form(
                step_id="action_required",
                data_schema=vol.Schema(
                    OrderedDict([(vol.Optional(CONF_PROXY, default=False), bool)])
                ),
                description_placeholders={
                    "email": login.email,
                    "url": login.url,
                    "message": f"  \n>{login.status.get('message','')}  \n",
                },
            )
        if login.status and (login.status.get("login_failed")):
            if login.oauth_login:
                _LOGGER.debug("Trying non-oauth login")
                await login.reset()
                login.oauth_login = False
                await login.login()
                return await self._test_login()
            _LOGGER.debug("Login failed: %s", login.status.get("login_failed"))
            await login.close()
            self.hass.components.persistent_notification.async_dismiss(
                f"alexa_media_{slugify(email)}{slugify(login.url[7:])}"
            )
            return self.async_abort(reason="login_failed")
        new_schema = self._update_schema_defaults()
        if login.status and login.status.get("error_message"):
            _LOGGER.debug("Login error detected: %s", login.status.get("error_message"))
            if (
                login.status.get("error_message")
                in {
                    "There was a problem\n            Enter a valid email or mobile number\n          "
                }
                and self.automatic_steps < 2
            ):
                _LOGGER.debug(
                    "Trying automatic resubmission %s for error_message 'valid email'",
                    self.automatic_steps,
                )
                self.automatic_steps += 1
                await sleep(5)
                return await self.async_step_user_legacy(user_input=self.config)
            _LOGGER.debug(
                "Done with automatic resubmission for error_message 'valid email'; returning error message",
            )
            self.automatic_steps = 0
            return self.async_show_form(
                step_id="user_legacy",
                data_schema=vol.Schema(new_schema),
                description_placeholders={
                    "message": f"  \n> {login.status.get('error_message','')}"
                },
            )
        self.automatic_steps = 0
        return self.async_show_form(
            step_id="user_legacy",
            data_schema=vol.Schema(new_schema),
            description_placeholders={
                "message": f"  \n> {login.status.get('error_message','')}"
            },
        )

    def _save_user_input_to_config(self, user_input=None) -> None:
        """Process user_input to save to self.config.

        user_input can be a dictionary of strings or an internally
        saved config_entry data entry. This function will convert all to internal strings.

        """
        if user_input is None:
            return
        if CONF_PROXY in user_input:
            self.config[CONF_PROXY] = user_input[CONF_PROXY]
        if CONF_OAUTH_LOGIN in user_input:
            self.config[CONF_OAUTH_LOGIN] = user_input[CONF_OAUTH_LOGIN]
        if CONF_HASS_URL in user_input:
            self.config[CONF_HASS_URL] = user_input[CONF_HASS_URL]
        self.securitycode = user_input.get(CONF_SECURITYCODE)
        if self.securitycode is not None:
            self.config[CONF_SECURITYCODE] = self.securitycode
        elif CONF_SECURITYCODE in self.config:
            self.config.pop(CONF_SECURITYCODE)
        if user_input.get(CONF_OTPSECRET) and user_input.get(CONF_OTPSECRET).replace(
            " ", ""
        ):
            self.config[CONF_OTPSECRET] = user_input[CONF_OTPSECRET].replace(" ", "")
        elif user_input.get(CONF_OTPSECRET):
            # a blank line
            self.config.pop(CONF_OTPSECRET)
        if CONF_EMAIL in user_input:
            self.config[CONF_EMAIL] = user_input[CONF_EMAIL]
        if CONF_PASSWORD in user_input:
            self.config[CONF_PASSWORD] = user_input[CONF_PASSWORD]
        if CONF_URL in user_input:
            self.config[CONF_URL] = user_input[CONF_URL]
        if CONF_DEBUG in user_input:
            self.config[CONF_DEBUG] = user_input[CONF_DEBUG]
        if CONF_SCAN_INTERVAL in user_input:
            self.config[CONF_SCAN_INTERVAL] = (
                user_input[CONF_SCAN_INTERVAL]
                if not isinstance(user_input[CONF_SCAN_INTERVAL], timedelta)
                else user_input[CONF_SCAN_INTERVAL].total_seconds()
            )
        if CONF_INCLUDE_DEVICES in user_input:
            if isinstance(user_input[CONF_INCLUDE_DEVICES], list):
                self.config[CONF_INCLUDE_DEVICES] = (
                    reduce(lambda x, y: f"{x},{y}", user_input[CONF_INCLUDE_DEVICES])
                    if user_input[CONF_INCLUDE_DEVICES]
                    else ""
                )
            else:
                self.config[CONF_INCLUDE_DEVICES] = user_input[CONF_INCLUDE_DEVICES]
        if CONF_EXCLUDE_DEVICES in user_input:
            if isinstance(user_input[CONF_EXCLUDE_DEVICES], list):
                self.config[CONF_EXCLUDE_DEVICES] = (
                    reduce(lambda x, y: f"{x},{y}", user_input[CONF_EXCLUDE_DEVICES])
                    if user_input[CONF_EXCLUDE_DEVICES]
                    else ""
                )
            else:
                self.config[CONF_EXCLUDE_DEVICES] = user_input[CONF_EXCLUDE_DEVICES]
        if (
            user_input.get(CONF_COOKIES_TXT)
            and f"{HTTP_COOKIE_HEADER}\n" != user_input[CONF_COOKIES_TXT]
        ):
            fixed_cookies_txt = re.sub(
                r" ",
                r"\n",
                re.sub(
                    r"#.*\n",
                    r"",
                    re.sub(
                        r"# ((?:.(?!# ))+)$",
                        r"\1",
                        re.sub(r" #", r"\n#", user_input[CONF_COOKIES_TXT]),
                    ),
                ),
            )
            if not fixed_cookies_txt.startswith(HTTP_COOKIE_HEADER):
                fixed_cookies_txt = f"{HTTP_COOKIE_HEADER}\n{fixed_cookies_txt}"
            self.config[CONF_COOKIES_TXT] = fixed_cookies_txt
            _LOGGER.debug("Setting cookies to:\n%s", fixed_cookies_txt)

    def _update_schema_defaults(self) -> Any:
        new_schema = self._update_ord_dict(
            self.data_schema,
            {
                vol.Required(CONF_EMAIL, default=self.config.get(CONF_EMAIL, "")): str,
                vol.Required(
                    CONF_PASSWORD, default=self.config.get(CONF_PASSWORD, "")
                ): str,
                vol.Optional(
                    CONF_SECURITYCODE,
                    default=self.securitycode if self.securitycode else "",
                ): str,
                vol.Optional(
                    CONF_OTPSECRET,
                    default=self.config.get(CONF_OTPSECRET, ""),
                ): str,
                vol.Required(
                    CONF_URL, default=self.config.get(CONF_URL, "amazon.com")
                ): str,
                vol.Optional(
                    CONF_DEBUG, default=bool(self.config.get(CONF_DEBUG, False))
                ): bool,
                vol.Optional(
                    CONF_INCLUDE_DEVICES,
                    default=self.config.get(CONF_INCLUDE_DEVICES, ""),
                ): str,
                vol.Optional(
                    CONF_EXCLUDE_DEVICES,
                    default=self.config.get(CONF_EXCLUDE_DEVICES, ""),
                ): str,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=self.config.get(CONF_SCAN_INTERVAL, 60)
                ): int,
                vol.Optional(
                    CONF_COOKIES_TXT, default=self.config.get(CONF_COOKIES_TXT, "")
                ): str,
                vol.Optional(
                    CONF_OAUTH_LOGIN, default=self.config.get(CONF_OAUTH_LOGIN, True)
                ): bool,
            },
        )
        return new_schema

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for Alexa Media."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_QUEUE_DELAY,
                    default=self.config_entry.options.get(
                        CONF_QUEUE_DELAY, DEFAULT_QUEUE_DELAY
                    ),
                ): vol.All(vol.Coerce(float), vol.Clamp(min=0)),
                vol.Required(
                    CONF_EXTENDED_ENTITY_DISCOVERY,
                    default=self.config_entry.options.get(
                        CONF_EXTENDED_ENTITY_DISCOVERY,
                        DEFAULT_EXTENDED_ENTITY_DISCOVERY,
                    ),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)


class AlexaMediaAuthorizationCallbackView(HomeAssistantView):
    """Handle callback from external auth."""

    url = AUTH_CALLBACK_PATH
    name = AUTH_CALLBACK_NAME
    requires_auth = False

    async def get(self, request: web.Request):
        """Receive authorization confirmation."""
        hass = request.app["hass"]
        try:
            await hass.config_entries.flow.async_configure(
                flow_id=request.query["flow_id"], user_input=None
            )
        except (KeyError, UnknownFlow) as ex:
            _LOGGER.debug("Callback flow_id is invalid.")
            raise HTTPBadRequest() from ex
        return web_response.Response(
            headers={"content-type": "text/html"},
            text="<script>window.close()</script>Success! This window can be closed",
        )


class AlexaMediaAuthorizationProxyView(HomeAssistantView):
    """Handle proxy connections."""

    url: Text = AUTH_PROXY_PATH
    extra_urls: List[Text] = [f"{AUTH_PROXY_PATH}/{{tail:.*}}"]
    name: Text = AUTH_PROXY_NAME
    requires_auth: bool = False
    handler: web.RequestHandler = None
    known_ips: Dict[Text, datetime.datetime] = {}
    auth_seconds: int = 300

    def __init__(self, handler: web.RequestHandler):
        """Initialize routes for view.

        Args:
            handler (web.RequestHandler): Handler to apply to all method types

        """
        AlexaMediaAuthorizationProxyView.handler = handler
        for method in ("get", "post", "delete", "put", "patch", "head", "options"):
            setattr(self, method, self.check_auth())

    @classmethod
    def check_auth(cls):
        """Wrap authentication into the handler."""

        async def wrapped(request, **kwargs):
            """Notify that the API is running."""
            hass = request.app["hass"]
            success = False
            if (
                request.remote not in cls.known_ips
                or (datetime.datetime.now() - cls.known_ips.get(request.remote)).seconds
                > cls.auth_seconds
            ):
                try:
                    flow_id = request.url.query["config_flow_id"]
                except KeyError as ex:
                    raise Unauthorized() from ex
                for flow in hass.config_entries.flow.async_progress():
                    if flow["flow_id"] == flow_id:
                        _LOGGER.debug(
                            "Found flow_id; adding %s to known_ips for %s seconds",
                            request.remote,
                            cls.auth_seconds,
                        )
                        success = True
                if not success:
                    raise Unauthorized()
                cls.known_ips[request.remote] = datetime.datetime.now()
            return await cls.handler(request, **kwargs)

        return wrapped

    @classmethod
    def reset(cls) -> None:
        """Reset the view."""
        cls.known_ips = {}
