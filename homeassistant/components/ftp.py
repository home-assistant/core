"""
A simple FTP server component
"""
# pylint: disable=import-error
from pyftpdlib.authorizers import DummyAuthorizer
# pylint: disable=import-error
from pyftpdlib.handlers import FTPHandler
# pylint: disable=import-error
from pyftpdlib.servers import FTPServer
import homeassistant as ha
from homeassistant.const import (
    CONF_USERNAME,
    CONF_PASSWORD,
    EVENT_FTP_FILE_RECEIVED)
import threading
# pylint: disable=import-error
from socketserver import ThreadingMixIn
import logging
import os
import homeassistant.util as util

DOMAIN = "ftp"

CONF_SERVER_HOST = "server_host"
CONF_SERVER_PORT = "server_port"
CONF_FTP_ROOT = "ftp_root"

DEFAULT_FTP_DIR = 'ftp_files'

DEPENDENCIES = []

_LOGGER = logging.getLogger(__name__)

FTP_SERVER = None


def setup(hass, config=None):
    """ Sets up the HTTP API and debug interface. """
    # pylint: disable=global-statement, import-error
    global FTP_SERVER

    if config is None or DOMAIN not in config:
        config = {DOMAIN: {}}

    # If no server host is given, accept all incoming requests
    server_host = config[DOMAIN].get(CONF_SERVER_HOST, '')

    server_port = config[DOMAIN].get(CONF_SERVER_PORT, 1121)

    username = config[DOMAIN].get(CONF_USERNAME, 'user')

    password = config[DOMAIN].get(CONF_PASSWORD, '12345')

    ftp_root_path = config[DOMAIN].get(
        CONF_FTP_ROOT,
        os.path.join(
            hass.config.config_dir,
            DEFAULT_FTP_DIR))

    if not os.path.isdir(ftp_root_path):
        os.makedirs(ftp_root_path)
        _LOGGER.info('FTP component root path did not exist and was \
            automatically created at %s', ftp_root_path)

    server = HomeAssistantFTPServer(
        (server_host, server_port), FtpRequestHandler, hass,
        username, password, ftp_root_path)

    FTP_SERVER = server

    hass.bus.listen_once(
        ha.EVENT_HOMEASSISTANT_START,
        lambda event:
        threading.Thread(target=server.start, daemon=True).start())

    return True


class HomeAssistantFTPServer(ThreadingMixIn, FTPServer):
    """ A simple multi-thread FTP server """
    # pylint: disable=too-many-arguments
    # pylint: disable=super-on-old-class
    def __init__(self, server_address, request_handler_class,
                 hass, username, password, ftp_root_path):
        self._ftp_root_path = ftp_root_path
        self._username = username
        self._password = password

        authorizer = DummyAuthorizer()
        authorizer.add_user(
            self._username,
            self._password,
            self._ftp_root_path,
            perm="elradfmw")

        request_handler_class.authorizer = authorizer
        # pylint: disable=super-on-old-class
        super().__init__(server_address, request_handler_class)

        self._server_address = server_address
        self.hass = hass

    def start(self):
        """ Starts the server. """
        # pylint: disable=no-member
        self.hass.bus.listen_once(
            ha.EVENT_HOMEASSISTANT_STOP,
            lambda event: self.close_all())

        _LOGGER.info(
            "Starting ftp serfer at ftp://%s:%d", *self._server_address)

        # pylint: disable=no-member
        self.serve_forever()

    @property
    def username(self):
        """ The configured FTP username """
        return self._username

    @property
    def password(self):
        """ The configured FTP password """
        return self._password

    @property
    def server_port(self):
        """ The configured FTP server port, should be > 1024
        if not running as root """
        return self._server_address[1]

    # pylint: disable=no-self-use
    # pylint: disable=super-on-old-class
    @property
    def server_ip(self):
        """ The LAN IP of the FTP server """
        return util.get_local_ip()

    @property
    def ftp_root_path(self):
        """ The local root directory for FTP uploads """
        return self._ftp_root_path


# pylint: disable=no-init
# pylint: disable=too-few-public-methods
class FtpRequestHandler(FTPHandler):
    """ Handler for FTP Requests """
    def on_file_received(self, uploaded_file):
        """ Fires the ftp_file_received event on successfull upload """
        # pylint: disable=no-member
        self.server.hass.bus.fire(
            EVENT_FTP_FILE_RECEIVED,
            {"component": DOMAIN, "file_name": uploaded_file})
