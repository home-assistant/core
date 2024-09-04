"""Support for functionality to download files."""

from __future__ import annotations

from http import HTTPStatus
import os
import re
import threading

import requests
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    HomeAssistant,
    ServiceCall,
)
from homeassistant.data_entry_flow import FlowResultType
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import raise_if_invalid_filename, raise_if_invalid_path

from .const import (
    _LOGGER,
    ATTR_FILENAME,
    ATTR_OVERWRITE,
    ATTR_SUBDIR,
    ATTR_URL,
    CONF_DOWNLOAD_DIR,
    DOMAIN,
    DOWNLOAD_COMPLETED_EVENT,
    DOWNLOAD_FAILED_EVENT,
    SERVICE_DOWNLOAD_FILE,
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_DOWNLOAD_DIR): cv.string})},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Downloader component, via the YAML file."""
    if DOMAIN not in config:
        return True

    hass.async_create_task(_async_import_config(hass, config))
    return True


async def _async_import_config(hass: HomeAssistant, config: ConfigType) -> None:
    """Import the Downloader component from the YAML file."""

    import_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_DOWNLOAD_DIR: config[DOMAIN][CONF_DOWNLOAD_DIR],
        },
    )

    if (
        import_result["type"] == FlowResultType.ABORT
        and import_result["reason"] != "single_instance_allowed"
    ):
        async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2024.10.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="directory_does_not_exist",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Downloader",
                "url": "/config/integrations/dashboard/add?domain=downloader",
            },
        )
    else:
        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2024.10.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Downloader",
            },
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Listen for download events to download files."""
    download_path = entry.data[CONF_DOWNLOAD_DIR]

    # If path is relative, we assume relative to Home Assistant config dir
    if not os.path.isabs(download_path):
        download_path = hass.config.path(download_path)

    if not await hass.async_add_executor_job(os.path.isdir, download_path):
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

                if subdir:
                    # Check the path
                    raise_if_invalid_path(subdir)

                final_path = None

                req = requests.get(url, stream=True, timeout=10)

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

        threading.Thread(target=do_download).start()

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_DOWNLOAD_FILE,
        download_file,
        schema=vol.Schema(
            {
                vol.Optional(ATTR_FILENAME): cv.string,
                vol.Optional(ATTR_SUBDIR): cv.string,
                vol.Required(ATTR_URL): cv.url,
                vol.Optional(ATTR_OVERWRITE, default=False): cv.boolean,
            }
        ),
    )

    return True
