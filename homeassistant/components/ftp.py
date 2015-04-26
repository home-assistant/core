from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer
import homeassistant as ha
from homeassistant.const import (
	CONF_USERNAME, CONF_PASSWORD,
    EVENT_FTP_FILE_RECEIVED)
import threading
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

ftp_server = None


def setup(hass, config=None):
    """ Sets up the HTTP API and debug interface. """
    # pylint: disable=global-statement, import-error
    global ftp_server

    if config is None or DOMAIN not in config:
        config = {DOMAIN: {}}

    # If no server host is given, accept all incoming requests
    server_host = config[DOMAIN].get(CONF_SERVER_HOST, '')

    server_port = config[DOMAIN].get(CONF_SERVER_PORT, 1121)

    username = config[DOMAIN].get(CONF_USERNAME, 'user')

    password = config[DOMAIN].get(CONF_PASSWORD, '12345')

    ftp_root_path = config[DOMAIN].get(CONF_FTP_ROOT, os.path.join(hass.config.config_dir, DEFAULT_FTP_DIR))

    if not os.path.isdir(ftp_root_path):
        os.makedirs(ftp_root_path)
        _LOGGER.info('FTP component root path did not exist and was atomatically created at {0}'.format(ftp_root_path))

    server = HomeAssistantFTPServer(
        (server_host, server_port), FtpRequestHandler, hass,
        username, password, ftp_root_path)

    ftp_server = server

    hass.bus.listen_once(
        ha.EVENT_HOMEASSISTANT_START,
        lambda event:
        threading.Thread(target=server.start, daemon=True).start())

    # hass.http = server
    # hass.config.api = rem.API(util.get_local_ip(), api_password, server_port)

    return True


class HomeAssistantFTPServer(ThreadingMixIn, FTPServer):

    def __init__(self, server_address, request_handler_class,
                 hass, username, password, ftp_root_path):
        self._ftp_root_path = ftp_root_path
        self._username = username
        self._password = password

        authorizer = DummyAuthorizer()
        authorizer.add_user(self._username, self._password, self._ftp_root_path, perm="elradfmw")
        #authorizer.add_anonymous("/home/user0/Downloads")
        request_handler_class.authorizer = authorizer

        super().__init__(server_address, request_handler_class)

        self._server_address = server_address
        self.hass = hass

        # server = FTPServer(("127.0.0.1", 21), handler)
        # server.serve_forever()

    def start(self):
        """ Starts the server. """
        self.hass.bus.listen_once(
            ha.EVENT_HOMEASSISTANT_STOP,
            lambda event: self.close_all())

        _LOGGER.info(
            "Starting ftp serfer at ftp://%s:%d", *self._server_address)

        self.serve_forever()

    @property
    def username(self):
        return self._username

    @property
    def password(self):
        return self._password

    @property
    def server_port(self):
        return self._server_address[1]

    @property
    def server_ip(self):
        return util.get_local_ip()

    @property
    def ftp_root_path(self):
        return self._ftp_root_path


class FtpRequestHandler(FTPHandler):

    def on_file_received(self, file):
        self.server.hass.bus.fire(
                EVENT_FTP_FILE_RECEIVED, {"component": DOMAIN,
                "file_name": file})
        pass