"""
homeassistant.components.downloader
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides functionality to download files.
"""
import os
import logging
import re
import threading

import homeassistant.util as util

DOMAIN = "downloader"

SERVICE_DOWNLOAD_FILE = "download_file"


# pylint: disable=too-many-branches
def setup(bus, download_path):
    """ Listens for download events to download files. """

    logger = logging.getLogger(__name__)

    try:
        import requests
    except ImportError:
        logger.exception(("Failed to import requests. "
                          "Did you maybe not execute 'pip install requests'?"))

        return False

    if not os.path.isdir(download_path):

        logger.error(
            ("Download path {} does not exist. File Downloader not active.").
            format(download_path))

        return False

    def download_file(service):
        """ Starts thread to download file specified in the url. """

        if not 'url' in service.data:
            logger.error("Service called but 'url' parameter not specified.")
            return

        def do_download():
            """ Downloads the file. """
            try:
                url = service.data['url']
                req = requests.get(url, stream=True)

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
                    filename = util.sanitize_filename(filename)

                    path, ext = os.path.splitext(os.path.join(download_path,
                                                              filename))

                    # If file exist append a number.
                    # We test filename, filename_2..
                    tries = 1
                    final_path = path + ext
                    while os.path.isfile(final_path):
                        tries += 1

                        final_path = path + "_{}".format(tries) + ext

                    logger.info("{} -> {}".format(
                                url, final_path))

                    with open(final_path, 'wb') as fil:
                        for chunk in req.iter_content(1024):
                            fil.write(chunk)

                    logger.info("Downloading of {} done".format(
                        url))

            except requests.exceptions.ConnectionError:
                logger.exception("ConnectionError occured for {}".
                                 format(url))

        threading.Thread(target=do_download).start()

    bus.register_service(DOMAIN, SERVICE_DOWNLOAD_FILE,
                         download_file)

    return True
