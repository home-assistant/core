"""
homeassistant.components.downloader
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides functionality to download files.
"""
import os
import logging
import re

import requests

import homeassistant.util as util

DOMAIN = "downloader"

SERVICE_DOWNLOAD_FILE = "download_file"


def setup(bus, download_path):
    """ Listens for download events to download files. """

    logger = logging.getLogger(__name__)

    if not os.path.isdir(download_path):

        logger.error(
            ("FileDownloader:"
             "Download path {} does not exist. File Downloader not active.").
            format(download_path))

        return False

    def _download_file(service):
        """ Downloads file specified in the url. """

        try:
            req = requests.get(service.data['url'], stream=True)
            if req.status_code == 200:
                filename = None

                if 'content-disposition' in req.headers:
                    match = re.findall(r"filename=(\S+)",
                                       req.headers['content-disposition'])

                    if len(match) > 0:
                        filename = match[0].strip("'\" ")

                if not filename:
                    filename = os.path.basename(service.data['url']).strip()

                if not filename:
                    filename = "ha_download"

                # Remove stuff to ruin paths
                filename = util.sanitize_filename(filename)

                path, ext = os.path.splitext(os.path.join(download_path,
                                                          filename))

                # If file exist append a number. We test filename, filename_2..
                tries = 1
                final_path = path + ext
                while os.path.isfile(final_path):
                    tries += 1

                    final_path = path + "_{}".format(tries) + ext

                logger.info("FileDownloader:{} -> {}".format(
                            service.data['url'], final_path))

                with open(final_path, 'wb') as fil:
                    for chunk in req.iter_content(1024):
                        fil.write(chunk)

        except requests.exceptions.ConnectionError:
            logger.exception("FileDownloader:ConnectionError occured for {}".
                             format(service.data['url']))

    bus.register_service(DOMAIN, SERVICE_DOWNLOAD_FILE,
                         _download_file)

    return True
