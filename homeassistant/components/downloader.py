"""
Support for functionality to download files.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/downloader/
"""
import logging
import os
import re
import threading

import requests
import voluptuous as vol

from homeassistant.helpers import validate_config
import homeassistant.helpers.config_validation as cv
from homeassistant.util import sanitize_filename

DOMAIN = "downloader"

SERVICE_DOWNLOAD_FILE = "download_file"

ATTR_URL = "url"
ATTR_SUBDIR = "subdir"

SERVICE_DOWNLOAD_FILE_SCHEMA = vol.Schema({
    vol.Required(ATTR_URL): vol.Url,
    vol.Optional(ATTR_SUBDIR): cv.string,
})

CONF_DOWNLOAD_DIR = 'download_dir'


# pylint: disable=too-many-branches
def setup(hass, config):
    """Listen for download events to download files."""
    logger = logging.getLogger(__name__)

    if not validate_config(config, {DOMAIN: [CONF_DOWNLOAD_DIR]}, logger):
        return False

    download_path = config[DOMAIN][CONF_DOWNLOAD_DIR]

    # If path is relative, we assume relative to HASS config dir
    if not os.path.isabs(download_path):
        download_path = hass.config.path(download_path)

    if not os.path.isdir(download_path):

        logger.error(
            "Download path %s does not exist. File Downloader not active.",
            download_path)

        return False

    def download_file(service):
        """Start thread to download file specified in the URL."""
        def do_download():
            """Download the file."""
            try:
                url = service.data[ATTR_URL]

                subdir = service.data.get(ATTR_SUBDIR)

                if subdir:
                    subdir = sanitize_filename(subdir)

                final_path = None

                req = requests.get(url, stream=True, timeout=10)

                if req.status_code == 200:
                    filename = None

                    if 'content-disposition' in req.headers:
                        match = re.findall(r"filename=(\S+)",
                                           req.headers['content-disposition'])

                        if len(match) > 0:
                            filename = match[0].strip("'\" ")

                    if not filename:
                        filename = os.path.basename(
                            url).strip()

                    if not filename:
                        filename = "ha_download"

                    # Remove stuff to ruin paths
                    filename = sanitize_filename(filename)

                    # Do we want to download to subdir, create if needed
                    if subdir:
                        subdir_path = os.path.join(download_path, subdir)

                        # Ensure subdir exist
                        if not os.path.isdir(subdir_path):
                            os.makedirs(subdir_path)

                        final_path = os.path.join(subdir_path, filename)

                    else:
                        final_path = os.path.join(download_path, filename)

                    path, ext = os.path.splitext(final_path)

                    # If file exist append a number.
                    # We test filename, filename_2..
                    tries = 1
                    final_path = path + ext
                    while os.path.isfile(final_path):
                        tries += 1

                        final_path = "{}_{}.{}".format(path, tries, ext)

                    logger.info("%s -> %s", url, final_path)

                    with open(final_path, 'wb') as fil:
                        for chunk in req.iter_content(1024):
                            fil.write(chunk)

                    logger.info("Downloading of %s done", url)

            except requests.exceptions.ConnectionError:
                logger.exception("ConnectionError occured for %s", url)

                # Remove file if we started downloading but failed
                if final_path and os.path.isfile(final_path):
                    os.remove(final_path)

        threading.Thread(target=do_download).start()

    hass.services.register(DOMAIN, SERVICE_DOWNLOAD_FILE, download_file,
                           schema=SERVICE_DOWNLOAD_FILE_SCHEMA)

    return True
