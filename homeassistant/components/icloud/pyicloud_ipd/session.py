from typing import Any, Dict, NoReturn, Optional, Sequence
from typing_extensions import override
import typing
import inspect
import json
import logging
from requests import Session

from .exceptions import (
    PyiCloudAPIResponseException,
    PyiCloud2SARequiredException,
    PyiCloudServiceNotActivatedException,
)

LOGGER = logging.getLogger(__name__)

HEADER_DATA = {
    "X-Apple-ID-Account-Country": "account_country",
    "X-Apple-ID-Session-Id": "session_id",
    "X-Apple-Session-Token": "session_token",
    "X-Apple-TwoSV-Trust-Token": "trust_token",
    "X-Apple-TwoSV-Trust-Eligible": "trust_eligible",
    "X-Apple-I-Rscd": "apple_rscd",
    "X-Apple-I-Ercd": "apple_ercd",
    "scnt": "scnt",
}


class PyiCloudPasswordFilter(logging.Filter):
    def __init__(self, password: str):
        super().__init__(password)

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if self.name in message:
            record.msg = message.replace(self.name, "********")
            record.args = [] # type: ignore[assignment] 

        return True


class PyiCloudSession(Session):
    """iCloud session."""

    def __init__(self, service: Any):
        self.service = service
        super().__init__()

    @override
    # type: ignore 
    def request(self, method: str, url, **kwargs):  

        # Charge logging to the right service endpoint
        callee = inspect.stack()[2]
        module = inspect.getmodule(callee[0])
        request_logger = logging.getLogger(module.__name__).getChild("http") #type: ignore[union-attr]
        if self.service.password_filter not in request_logger.filters:
            request_logger.addFilter(self.service.password_filter)

        request_logger.debug("%s %s %s", method, url, kwargs.get("data", ""))

        has_retried = kwargs.get("retried")
        kwargs.pop("retried", None)
        response = super().request(method, url, **kwargs)

        content_type = response.headers.get("Content-Type", "").split(";")[0]
        json_mimetypes = ["application/json", "text/json"]

        request_logger.debug(response.headers)

        for header, value in HEADER_DATA.items():
            if response.headers.get(header):
                session_arg = value
                self.service.session_data.update(
                    {session_arg: response.headers.get(header)}
                )

        # Save session_data to file
        with open(self.service.session_path, "w", encoding="utf-8") as outfile:
            json.dump(self.service.session_data, outfile)
            LOGGER.debug("Saved session data to file")

        # Save cookies to file
        self.cookies.save(ignore_discard=True, ignore_expires=True) # type: ignore[attr-defined]
        LOGGER.debug("Cookies saved to %s", self.service.cookiejar_path)

        if not response.ok and (
            content_type not in json_mimetypes
            or response.status_code in [421, 450, 500]
        ):
            try:
                # pylint: disable=protected-access
                fmip_url = self.service._get_webservice_url("findme")
                if (
                    has_retried is None
                    and response.status_code in [421, 450, 500]
                    and fmip_url in url
                ):
                    # Handle re-authentication for Find My iPhone
                    LOGGER.debug("Re-authenticating Find My iPhone service")
                    try:
                        # If 450, authentication requires a full sign in to the account
                        service = None if response.status_code == 450 else "find"
                        self.service.authenticate(True, service)

                    except PyiCloudAPIResponseException:
                        LOGGER.debug("Re-authentication failed")
                    kwargs["retried"] = True
                    return self.request(method, url, **kwargs)
            except Exception:
                pass

            if has_retried is None and response.status_code in [421, 450, 500]:
                api_error = PyiCloudAPIResponseException(
                    response.reason, str(response.status_code), True
                )
                request_logger.debug(api_error)
                kwargs["retried"] = True
                return self.request(method, url, **kwargs)

            self._raise_error(str(response.status_code), response.reason)

        if content_type not in json_mimetypes:
            if self.service.session_data.get("apple_rscd") == "401":
                code: Optional[str] = "401"
                reason: Optional[str] = "Invalid username/password combination."
                self._raise_error(code or "Unknown", reason or "Unknown")

            return response

        try:
            data = response.json() if response.status_code != 204 else {}
        except:  
            request_logger.warning("Failed to parse response with JSON mimetype")
            return response

        request_logger.debug(data)

        if isinstance(data, dict):
            if data.get("hasError"):
                errors: Optional[Sequence[Dict[str, Any]]] = typing.cast(Optional[Sequence[Dict[str, Any]]], data.get("service_errors"))
                # service_errors returns a list of dict
                #    dict includes the keys: code, title, message, supressDismissal
                # Assuming a single error for now
                # May need to revisit to capture and handle multiple errors
                if errors:
                    code = errors[0].get("code")
                    reason = errors[0].get("message")
                self._raise_error(code or "Unknown", reason or "Unknown")
            elif not data.get("success"):
                reason = data.get("errorMessage")
                reason = reason or data.get("reason")
                reason = reason or data.get("errorReason")
                if not reason and isinstance(data.get("error"), str):
                    reason = data.get("error")
                if not reason and data.get("error"):
                    reason = "Unknown reason"

                code = data.get("errorCode")
                if not code and data.get("serverErrorCode"):
                    code = data.get("serverErrorCode")
                if not code and data.get("error"):
                    code = data.get("error")

                if reason:
                    self._raise_error(code or "Unknown", reason)

        return response

    def _raise_error(self, code: str, reason: str) -> NoReturn:
        if (
            self.service.requires_2sa
            and reason == "Missing X-APPLE-WEBAUTH-TOKEN cookie"
        ):
            raise PyiCloud2SARequiredException(self.service.user["accountName"])
        if code in ("ZONE_NOT_FOUND", "AUTHENTICATION_FAILED"):
            reason = (
                "Please log into https://icloud.com/ to manually "
                "finish setting up your iCloud service"
            )
            api_error: Exception = PyiCloudServiceNotActivatedException(reason, code)
            LOGGER.error(api_error)

            raise (api_error)
        if code == "ACCESS_DENIED":
            reason = (
                reason + ".  Please wait a few minutes then try again."
                "The remote servers might be trying to throttle requests."
            )
        if code in ["421", "450", "500"]:
            reason = "Authentication required for Account."

        api_error = PyiCloudAPIResponseException(reason, code)
        LOGGER.error(api_error)
        raise api_error

