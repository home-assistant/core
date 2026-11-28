"""Config flow to configure the iCloud integration."""

from collections.abc import Mapping
from functools import partial
import logging
import os
from typing import TYPE_CHECKING, Any, override

import probatio
from pyicloud import PyiCloudService
from pyicloud.exceptions import (
    PyiCloud2FARequiredException,
    PyiCloudAcceptTermsException,
    PyiCloudAPIResponseException,
    PyiCloudAuthRequiredException,
    PyiCloudConnectionException,
    PyiCloudException,
    PyiCloudFailedLoginException,
    PyiCloudNoDevicesException,
    PyiCloudServiceNotActivatedException,
    PyiCloudServiceUnavailable,
)

from homeassistant.config_entries import (
    SOURCE_USER,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.storage import Store

from .account import code_can_be_delivered, is_2fa_status, is_auth_error
from .const import (
    CONF_GPS_ACCURACY_THRESHOLD,
    CONF_INCLUDE_COMPLETED,
    CONF_MAX_INTERVAL,
    CONF_WITH_FAMILY,
    DEFAULT_GPS_ACCURACY_THRESHOLD,
    DEFAULT_INCLUDE_COMPLETED,
    DEFAULT_MAX_INTERVAL,
    DEFAULT_WITH_FAMILY,
    DOMAIN,
    STORAGE_KEY,
    STORAGE_VERSION,
)

CONF_TRUSTED_DEVICE = "trusted_device"
CONF_VERIFICATION_CODE = "verification_code"
CONF_REQUEST_NEW_CODE = "request_new_code"
TERMS_URL = "https://www.icloud.com/terms"

_LOGGER = logging.getLogger(__name__)


class IcloudFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle an iCloud config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize iCloud config flow."""
        self.api = None
        self._username = None
        self._password = None
        self._api_login: tuple[str | None, str | None] | None = None
        self._with_family = None
        self._max_interval = None
        self._gps_accuracy_threshold = None
        self._include_completed = None

        self._trusted_device = None
        self._verification_code = None
        self._forced_2fa = False

        self._accept_terms = False
        self._resume_step_id = "user"

        self._existing_entry_data: dict[str, Any] | None = None
        self._description_placeholders: dict[str, str] | None = None

    @property
    def _requires_2fa(self) -> bool:
        """Return True when a 2FA code is what this flow has to collect.

        iCloud can raise a challenge from a request pyicloud does not route
        through authenticate(), which leaves api.requires_2fa false while a
        code is outstanding. The account records that case, and the flow has
        to honour it both when routing to the code form and when validating
        what is entered there.
        """
        return self._forced_2fa or bool(self.api and self.api.requires_2fa)

    def _show_setup_form(self, user_input=None, errors=None, step_id="user"):
        """Show the setup form to the user."""

        if user_input is None:
            user_input = {}

        if step_id == "user":
            schema = {
                probatio.Required(
                    CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")
                ): str,
                probatio.Required(
                    probatio.Secret(CONF_PASSWORD),
                    default=user_input.get(CONF_PASSWORD, ""),
                ): str,
                probatio.Optional(
                    CONF_WITH_FAMILY,
                    default=user_input.get(CONF_WITH_FAMILY, DEFAULT_WITH_FAMILY),
                ): bool,
                probatio.Optional(
                    CONF_INCLUDE_COMPLETED,
                    default=user_input.get(
                        CONF_INCLUDE_COMPLETED, DEFAULT_INCLUDE_COMPLETED
                    ),
                ): bool,
            }
        else:
            schema = {
                probatio.Required(
                    probatio.Secret(CONF_PASSWORD),
                    default=user_input.get(CONF_PASSWORD, ""),
                ): str,
            }

        return self.async_show_form(
            step_id=step_id,
            data_schema=probatio.Schema(schema),
            errors=errors or {},
            description_placeholders=self._description_placeholders,
        )

    async def _retry_without_stored_session(
        self, error: Exception, user_input, step_id
    ) -> ConfigFlowResult | None:
        """Log in again without the session iCloud rejected.

        PyiCloudService validates the stored session while it is constructed,
        so a rejected one fails before the password is tried and re-entering
        it would run into the same rejection. Returns a form to show when the
        login cannot be completed, or None when it succeeded.
        """
        _LOGGER.debug(
            "Stored iCloud session for %s was rejected, logging in again: %s",
            self._username,
            error,
        )
        storage_path = Store(self.hass, STORAGE_VERSION, STORAGE_KEY).path
        try:
            self.api, challenged = await self.hass.async_add_executor_job(
                self._login_without_stored_session, storage_path
            )
        except PyiCloudFailedLoginException as retry_error:
            _LOGGER.error("Error logging into iCloud service: %s", retry_error)
            self.api = None
            return self._show_setup_form(
                user_input, {CONF_PASSWORD: "invalid_auth"}, step_id
            )
        except PyiCloudAcceptTermsException as retry_error:
            return await self._async_terms_required(retry_error)
        except PyiCloudConnectionException as retry_error:
            _LOGGER.error("Error connecting to iCloud service: %s", retry_error)
            self.api = None
            return self._show_setup_form(
                user_input, {"base": "cannot_connect"}, step_id
            )
        except (
            PyiCloudAuthRequiredException,
            PyiCloudAPIResponseException,
        ) as retry_error:
            _LOGGER.error(
                "Could not log in to iCloud for %s: %s", self._username, retry_error
            )
            self.api = None
            return self._show_setup_form(user_input, {"base": "unknown"}, step_id)

        # A login that ended in a challenge rather than a failure leaves a
        # session that is what the code has to go through.
        self._forced_2fa = self._forced_2fa or challenged
        return None

    def _login_without_stored_session(
        self, storage_path: str
    ) -> tuple[PyiCloudService, bool]:
        """Log in with the stored session discarded, in the executor.

        The service validates the stored session while it is constructed, so
        it has to be built without authenticating for the session to be
        cleared before the login is attempted. Returns the service and whether
        the login ended in a 2FA challenge.
        """
        api = PyiCloudService(
            self._username,
            self._password,
            storage_path,
            with_family=self._with_family,
            authenticate=False,
            refresh_interval=None,
            accept_terms=self._accept_terms,
        )
        api.session.clear_persistence()
        try:
            api.authenticate()
        except PyiCloud2FARequiredException:
            # The login got as far as a challenge, which is a session to send
            # a code through rather than a failure to report.
            return api, True
        except PyiCloudAPIResponseException as err:
            # The same challenge, carried by the status because the body was
            # not the hsa2 JSON the dedicated exception is raised for.
            if not is_2fa_status(err):
                raise
            return api, True
        return api, False

    async def _report_undeliverable_code(self, user_input, step_id):
        """Send the flow back to the password when no code can be sent.

        iCloud can report a challenge whose delivery route was never
        established, and the code entry form is then a dead end. Dropping the
        session sends the next attempt through a fresh login, which raises the
        challenge again with a route behind it.

        The forced challenge is cleared with the session it belonged to.
        _requires_2fa reads it as well, so leaving it set would send the next
        attempt back to this same dead end even once the login succeeds.
        """
        _LOGGER.error(
            "No way to send an iCloud verification code for %s", self._username
        )
        if self.api is not None:
            # Dropping the service only clears it from memory. The stored
            # session is what the next login reads back, and it is the one
            # that produced a challenge nothing can deliver a code for.
            # Clearing it touches the filesystem, so it goes to the executor.
            await self.hass.async_add_executor_job(self.api.session.clear_persistence)
        self.api = None
        self._forced_2fa = False
        return self._show_setup_form(
            user_input, {"base": "send_verification_code"}, step_id
        )

    async def _request_2fa_code(self, errors: dict[str, str]) -> dict[str, str]:
        """Request an Apple 2FA code."""
        if TYPE_CHECKING:
            assert self.api is not None

        try:
            result = await self.hass.async_add_executor_job(self.api.request_2fa_code)
        except PyiCloudException as error:
            _LOGGER.error("Failed to request iCloud 2FA verification code: %s", error)
            errors["base"] = "send_verification_code"
            return errors
        except Exception:
            _LOGGER.exception(
                "Unexpected error requesting iCloud 2FA verification code"
            )
            errors["base"] = "send_verification_code"
            return errors

        if result is False:
            _LOGGER.error("PyiCloud request_2fa_code returned False")
            errors["base"] = "send_verification_code"
            return errors

        _LOGGER.debug("Requested iCloud 2FA verification code")
        return errors

    def _credentials_input(self) -> dict[str, Any]:
        """Return the credentials collected so far in the shape of step input."""
        return {
            CONF_USERNAME: self._username,
            CONF_PASSWORD: self._password,
            CONF_WITH_FAMILY: self._with_family,
            CONF_MAX_INTERVAL: self._max_interval,
            CONF_GPS_ACCURACY_THRESHOLD: self._gps_accuracy_threshold,
            CONF_INCLUDE_COMPLETED: self._include_completed,
        }

    async def _validate_and_create_entry(self, user_input, step_id):
        """Check if config is valid and create entry if so."""

        extra_inputs = user_input
        self._resume_step_id = step_id

        # If an existing entry was found, meaning this is a password update attempt,
        # use those to get config values that aren't changing.
        if self._existing_entry_data:
            extra_inputs = self._existing_entry_data

        if user_input is not None and CONF_PASSWORD in user_input:
            extra_inputs[CONF_PASSWORD] = user_input[CONF_PASSWORD]

        self._username = extra_inputs[CONF_USERNAME]
        self._password = extra_inputs.get(CONF_PASSWORD, "")
        self._with_family = extra_inputs.get(CONF_WITH_FAMILY, DEFAULT_WITH_FAMILY)
        self._max_interval = extra_inputs.get(CONF_MAX_INTERVAL, DEFAULT_MAX_INTERVAL)
        self._gps_accuracy_threshold = extra_inputs.get(
            CONF_GPS_ACCURACY_THRESHOLD, DEFAULT_GPS_ACCURACY_THRESHOLD
        )
        self._include_completed = extra_inputs.get(
            CONF_INCLUDE_COMPLETED, DEFAULT_INCLUDE_COMPLETED
        )

        # A login kept through an outage belongs to the credentials it was made
        # with, not to whatever the form is submitted with next.
        login = (self._username, self._password)
        if self._api_login not in (None, login):
            self.api = None
        self._api_login = login

        # Check if already configured. The user flow can be submitted again with
        # another account, which then is the one that is checked and stored.
        if self.source == SOURCE_USER or self.unique_id is None:
            await self.async_set_unique_id(self._username)
            self._abort_if_unique_id_configured()

        if self.api is None:
            try:
                self.api = await self.hass.async_add_executor_job(
                    partial(
                        PyiCloudService,
                        self._username,
                        self._password,
                        Store(self.hass, STORAGE_VERSION, STORAGE_KEY).path,
                        with_family=self._with_family,
                        refresh_interval=None,
                        accept_terms=self._accept_terms,
                    )
                )
            except PyiCloudAcceptTermsException as error:
                return await self._async_terms_required(error)
            except PyiCloudFailedLoginException as error:
                _LOGGER.error("Error logging into iCloud service: %s", error)
                self.api = None
                errors = {CONF_PASSWORD: "invalid_auth"}
                return self._show_setup_form(user_input, errors, step_id)
            except PyiCloudConnectionException as error:
                _LOGGER.error("Error connecting to iCloud service: %s", error)
                self.api = None
                errors = {"base": "cannot_connect"}
                return self._show_setup_form(user_input, errors, step_id)
            except (
                PyiCloud2FARequiredException,
                PyiCloudAuthRequiredException,
                PyiCloudAPIResponseException,
            ) as error:
                if isinstance(
                    error, PyiCloudAPIResponseException
                ) and not is_auth_error(error):
                    # iCloud failing rather than refusing. The stored session
                    # is not at fault and must not be thrown away over an
                    # outage: it carries the trust token that keeps the user
                    # from being asked for a code again.
                    _LOGGER.error(
                        "Could not log in to iCloud for %s: %s", self._username, error
                    )
                    self.api = None
                    errors = {"base": "unknown"}
                    return self._show_setup_form(user_input, errors, step_id)
                result = await self._retry_without_stored_session(
                    error, user_input, step_id
                )
                if result is not None:
                    return result

        if self._requires_2fa:
            if not code_can_be_delivered(self.api):
                return await self._report_undeliverable_code(user_input, step_id)
            return await self.async_step_verification_code()

        if self.api.requires_2sa:
            return await self.async_step_trusted_device()

        try:
            devices = await self.hass.async_add_executor_job(
                getattr, self.api, "devices"
            )
            if not devices:
                raise PyiCloudNoDevicesException  # noqa: TRY301
        except PyiCloudServiceNotActivatedException, PyiCloudNoDevicesException:
            _LOGGER.error("No device found in the iCloud account: %s", self._username)
            self.api = None
            return self.async_abort(reason="no_device")
        except PyiCloudConnectionException as error:
            # Unreachable rather than refusing, so the session is kept as it is
            # for an outage.
            _LOGGER.error("Error connecting to iCloud service: %s", error)
            return self._show_setup_form(
                user_input, {"base": "cannot_connect"}, step_id
            )
        except PyiCloudServiceUnavailable as error:
            # iCloud failing rather than refusing. The stored session is not at
            # fault and must not be thrown away over an outage: it carries the
            # trust token that keeps the user from being asked for a code
            # again.
            _LOGGER.error("Could not reach iCloud for %s: %s", self._username, error)
            return self._show_setup_form(user_input, {"base": "unknown"}, step_id)
        except (
            PyiCloud2FARequiredException,
            PyiCloudAuthRequiredException,
            PyiCloudAPIResponseException,
            PyiCloudFailedLoginException,
        ) as error:
            # Reading the devices is where iCloud turns down a session that
            # logging in accepted, so a rejection here is the same one the
            # login paths report rather than a reason to end the flow with an
            # error the user cannot act on.
            if isinstance(error, PyiCloud2FARequiredException) or (
                isinstance(error, PyiCloudAPIResponseException) and is_2fa_status(error)
            ):
                if not code_can_be_delivered(self.api):
                    return await self._report_undeliverable_code(user_input, step_id)
                # The session that was challenged is the one the code has to
                # go through, so it is kept.
                self._forced_2fa = True
                return await self.async_step_verification_code()
            _LOGGER.error(
                "Could not read the devices of the iCloud account for %s: %s",
                self._username,
                error,
            )
            if not isinstance(error, PyiCloudAPIResponseException) or is_auth_error(
                error
            ):
                # iCloud is refusing the session rather than failing: the flow
                # starts again from the password, which builds a service
                # without it. An outage leaves it alone.
                self.api = None
            return self._show_setup_form(user_input, {"base": "unknown"}, step_id)

        data = self._credentials_input()

        # If this is a password update attempt, don't try creating a new one.
        if self.source == SOURCE_USER:
            return self.async_create_entry(title=self._username, data=data)

        entry = await self.async_set_unique_id(self.unique_id)
        self.hass.config_entries.async_update_entry(entry, data=data)
        await self.hass.config_entries.async_reload(entry.entry_id)
        return self.async_abort(reason="reauth_successful")

    async def _async_terms_required(
        self, error: PyiCloudAcceptTermsException
    ) -> ConfigFlowResult:
        """Drop the unusable session and ask the user to accept the terms."""
        _LOGGER.error(
            "Apple updated the iCloud terms of service and they must be "
            "accepted to continue: %s",
            error,
        )
        self.api = None
        # The challenge belonged to the session just dropped. Left set, it
        # would send the login that follows the acceptance back to code entry.
        self._forced_2fa = False
        # A login that already accepted them and still failed cannot be helped
        # by accepting again, so say so rather than offering the step in a loop.
        errors = {"base": "accept_terms_failed"} if self._accept_terms else None
        return await self.async_step_accept_terms(errors=errors)

    async def async_step_accept_terms(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Ask the user to accept Apple's updated terms of service."""
        if user_input is None:
            return self.async_show_form(
                step_id="accept_terms",
                data_schema=probatio.Schema({}),
                errors=errors or {},
                description_placeholders={"terms_url": TERMS_URL},
            )

        self._accept_terms = True
        # pyicloud only accepts the terms while authenticating, so the session
        # has to be built again for the acceptance to reach Apple.
        self.api = None
        return await self._validate_and_create_entry(
            self._credentials_input(), self._resume_step_id
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        icloud_dir = Store[Any](self.hass, STORAGE_VERSION, STORAGE_KEY)

        if not os.path.exists(icloud_dir.path):
            await self.hass.async_add_executor_job(os.makedirs, icloud_dir.path)

        if user_input is None:
            return self._show_setup_form(user_input, errors)

        return await self._validate_and_create_entry(user_input, "user")

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Initialise re-authentication."""
        # Store existing entry data so it can be used later and set unique ID
        # so existing config entry can be updated.
        await self.async_set_unique_id(self.context["unique_id"])
        self._existing_entry_data = {**entry_data}
        self._description_placeholders = {"username": entry_data[CONF_USERNAME]}

        # Get the API from the existing entry runtime data
        account = self._get_reauth_entry().runtime_data
        self.api = account.api

        # If the API is None, it means the existing entry was never successfully authenticated,
        # so we need to show the setup form again to get the password.
        if self.api is None:
            return self._show_setup_form(step_id="reauth_confirm")

        # Only meaningful together with the session it was raised on, which is
        # why it is read here rather than before the check above.
        self._forced_2fa = account.requires_verification_code

        # If the API is not None, it means the existing entry was successfully authenticated before,
        # so we can proceed to the reauth_confirm step to trigger 2FA challenge.
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Initialise re-authentication confirmation.

        Update password for a config entry that can't authenticate (if changed)
        and trigger 2FA challenge if needed.
        """
        return await self._validate_and_create_entry(user_input, "reauth_confirm")

    async def async_step_trusted_device(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """We need a trusted device."""
        if errors is None:
            errors = {}

        if TYPE_CHECKING:
            assert self.api is not None
        trusted_devices = await self.hass.async_add_executor_job(
            getattr, self.api, "trusted_devices"
        )
        trusted_devices_for_form = {}
        for i, device in enumerate(trusted_devices):
            trusted_devices_for_form[i] = device.get(
                "deviceName", f"SMS to {device.get('phoneNumber')}"
            )

        if user_input is None:
            return await self._show_trusted_device_form(
                trusted_devices_for_form, errors
            )

        self._trusted_device = trusted_devices[int(user_input[CONF_TRUSTED_DEVICE])]

        if not await self.hass.async_add_executor_job(
            self.api.send_verification_code, self._trusted_device
        ):
            _LOGGER.error("Failed to send verification code")
            self._trusted_device = None
            errors[CONF_TRUSTED_DEVICE] = "send_verification_code"

            return await self._show_trusted_device_form(
                trusted_devices_for_form, errors
            )

        return await self.async_step_verification_code()

    async def _show_trusted_device_form(
        self, trusted_devices, errors: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Show the trusted_device form to the user."""

        return self.async_show_form(
            step_id="trusted_device",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_TRUSTED_DEVICE): probatio.All(
                        probatio.Coerce(int), probatio.In(trusted_devices)
                    )
                }
            ),
            errors=errors or {},
        )

    async def async_step_verification_code(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Ask the verification code to the user."""
        if errors is None:
            errors = {}

        if user_input is None:
            return await self._show_verification_code_form(errors)

        if user_input[CONF_REQUEST_NEW_CODE]:
            # If the user requested a new code, request it
            errors = await self._request_2fa_code(errors)
            return await self._show_verification_code_form(errors)

        if user_input[CONF_VERIFICATION_CODE] == "":
            # If the user didn't provide a code, show the form again with an error
            errors["base"] = "validate_verification_code"
            return await self.async_step_verification_code(errors=errors)

        if TYPE_CHECKING:
            assert self.api is not None

        self._verification_code = user_input[CONF_VERIFICATION_CODE]

        try:
            if self._requires_2fa:
                if not await self.hass.async_add_executor_job(
                    self.api.validate_2fa_code, self._verification_code
                ):
                    raise PyiCloudException("The code you entered is not valid.")  # noqa: TRY301
            elif not await self.hass.async_add_executor_job(
                self.api.validate_verification_code,
                self._trusted_device,
                self._verification_code,
            ):
                raise PyiCloudException("The code you entered is not valid.")  # noqa: TRY301
        except PyiCloudAcceptTermsException as error:
            return await self._async_terms_required(error)
        except PyiCloudException as error:
            # Redisplay the verification form after a failed verification attempt.
            # For 2FA, do not request a new Apple verification code on every bad
            # user entry. The original code may still be valid, and repeatedly
            # requesting new codes can invalidate prior codes or trigger rate limits.
            _LOGGER.error("Failed to verify verification code: %s", error)
            self._trusted_device = None
            self._verification_code = None
            errors["base"] = "validate_verification_code"

            if self._requires_2fa:
                return await self.async_step_verification_code(errors=errors)

            return await self.async_step_trusted_device(errors=errors)

        # The challenge is answered; leaving this set would route the login
        # that follows straight back to this form.
        self._forced_2fa = False

        return await self.async_step_user(self._credentials_input())

    async def _show_verification_code_form(
        self, errors: dict[str, str]
    ) -> ConfigFlowResult:
        """Show the verification_code form to the user."""

        return self.async_show_form(
            step_id="verification_code",
            data_schema=probatio.Schema(
                {
                    probatio.Optional(CONF_VERIFICATION_CODE): str,
                    probatio.Optional(CONF_REQUEST_NEW_CODE, default=False): bool,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> IcloudOptionsFlowHandler:
        """Get the options flow for this handler."""
        return IcloudOptionsFlowHandler()


class IcloudOptionsFlowHandler(OptionsFlowWithReload):
    """Handle an iCloud options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the iCloud options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=probatio.Schema(
                {
                    probatio.Optional(
                        CONF_INCLUDE_COMPLETED,
                        default=self.config_entry.options.get(
                            CONF_INCLUDE_COMPLETED,
                            self.config_entry.data.get(
                                CONF_INCLUDE_COMPLETED, DEFAULT_INCLUDE_COMPLETED
                            ),
                        ),
                    ): bool,
                }
            ),
        )
