"""Support for functionality to download files."""
from __future__ import annotations

import enum
from http import HTTPStatus
import logging
import os
import re
import typing

import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import raise_if_invalid_filename, raise_if_invalid_path

_LOGGER = logging.getLogger(__name__)

ATTR_FILENAME = "filename"
ATTR_SUBDIR = "subdir"
ATTR_URL = "url"
ATTR_OVERWRITE = "overwrite"
ATTR_ASYNC = "async"
ATTR_AUTH_TYPE = "auth_type"
ATTR_USERNAME = "username"
ATTR_PASSWORD = "password"

CONF_DOWNLOAD_DIR = "download_dir"

DOMAIN = "downloader"
DOWNLOAD_FAILED_EVENT = "download_failed"
DOWNLOAD_COMPLETED_EVENT = "download_completed"

SERVICE_DOWNLOAD_FILE = "download_file"


class AuthType(enum.Enum):
    """Enum for the type of HTTP authentication."""

    none = "none"
    basic = "basic"
    digest = "digest"


SERVICE_DOWNLOAD_FILE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_URL): cv.url,
        vol.Optional(ATTR_SUBDIR): cv.string,
        vol.Optional(ATTR_FILENAME): cv.string,
        vol.Optional(ATTR_OVERWRITE, default=False): cv.boolean,
        vol.Optional(ATTR_ASYNC, default=True): cv.boolean,
        vol.Optional(ATTR_AUTH_TYPE): cv.enum(AuthType),
        vol.Optional(ATTR_USERNAME): cv.string,
        vol.Optional(ATTR_PASSWORD): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_DOWNLOAD_DIR): cv.string})},
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Listen for download events to download files."""
    download_path = config[DOMAIN][CONF_DOWNLOAD_DIR]

    # If path is relative, we assume relative to Home Assistant config dir
    if not os.path.isabs(download_path):
        download_path = hass.config.path(download_path)

    if not os.path.isdir(download_path):
        _LOGGER.error(
            "Download path %s does not exist. File Downloader not active", download_path
        )

        return False

    def download_file(service: ServiceCall) -> None:
        """Start thread to download file specified in the URL."""

        def do_download() -> None:
            """Download the file."""
            try:
                url = service.data[ATTR_URL]

                subdir = service.data.get(ATTR_SUBDIR)

                filename = service.data.get(ATTR_FILENAME)

                overwrite = service.data.get(ATTR_OVERWRITE)

                auth_type = service.data.get(ATTR_AUTH_TYPE)

                username = str(service.data.get(ATTR_USERNAME))

                password = str(service.data.get(ATTR_PASSWORD))

                auth_scheme: typing.Union[HTTPBasicAuth, HTTPDigestAuth, None] = None
                if auth_type == AuthType.basic:
                    auth_scheme = HTTPBasicAuth(username, password)
                elif auth_type == AuthType.digest:
                    auth_scheme = HTTPDigestAuth(username, password)

                if subdir:
                    # Check the path
                    raise_if_invalid_path(subdir)

                final_path = None

                req = requests.get(url, stream=True, timeout=10, auth=auth_scheme)

                if req.status_code != HTTPStatus.OK:
                    _LOGGER.warning(
                        "Downloading '%s' failed, status_code=%d", url, req.status_code
                    )
                    hass.bus.fire(
                        f"{DOMAIN}_{DOWNLOAD_FAILED_EVENT}",
                        {"url": url, "filename": filename},
                    )

                else:
                    if filename is None and "content-disposition" in req.headers:
                        match = re.findall(
                            r"filename=(\S+)", req.headers["content-disposition"]
                        )

                        if match:
                            filename = match[0].strip("'\" ")

                    if not filename:
                        filename = os.path.basename(url).strip()

                    if not filename:
                        filename = "ha_download"

                    # Check the filename
                    raise_if_invalid_filename(filename)

                    # Do we want to download to subdir, create if needed
                    if subdir:
                        subdir_path = os.path.join(download_path, subdir)

                        # Ensure subdir exist
                        os.makedirs(subdir_path, exist_ok=True)

                        final_path = os.path.join(subdir_path, filename)

                    else:
                        final_path = os.path.join(download_path, filename)

                    path, ext = os.path.splitext(final_path)

                    # If file exist append a number.
                    # We test filename, filename_2..
                    if not overwrite:
                        tries = 1
                        final_path = path + ext
                        while os.path.isfile(final_path):
                            tries += 1

                            final_path = f"{path}_{tries}.{ext}"

                    _LOGGER.debug("%s -> %s", url, final_path)

                    with open(final_path, "wb") as fil:
                        for chunk in req.iter_content(1024):
                            fil.write(chunk)

                    _LOGGER.debug("Downloading of %s done", url)
                    hass.bus.fire(
                        f"{DOMAIN}_{DOWNLOAD_COMPLETED_EVENT}",
                        {"url": url, "filename": filename},
                    )

            except requests.exceptions.ConnectionError:
                _LOGGER.exception("ConnectionError occurred for %s", url)
                hass.bus.fire(
                    f"{DOMAIN}_{DOWNLOAD_FAILED_EVENT}",
                    {"url": url, "filename": filename},
                )

                # Remove file if we started downloading but failed
                if final_path and os.path.isfile(final_path):
                    os.remove(final_path)
            except ValueError:
                _LOGGER.exception("Invalid value")
                hass.bus.fire(
                    f"{DOMAIN}_{DOWNLOAD_FAILED_EVENT}",
                    {"url": url, "filename": filename},
                )

                # Remove file if we started downloading but failed
                if final_path and os.path.isfile(final_path):
                    os.remove(final_path)

        is_async = service.data.get(ATTR_ASYNC)

        if is_async:
            hass.async_add_executor_job(do_download)
        else:
            do_download()

    hass.services.register(
        DOMAIN,
        SERVICE_DOWNLOAD_FILE,
        download_file,
        schema=SERVICE_DOWNLOAD_FILE_SCHEMA,
    )

    return True
