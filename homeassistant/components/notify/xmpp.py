"""
Jabber (XMPP) notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.xmpp/
"""
from concurrent.futures import TimeoutError as FutTimeoutError
import logging
import mimetypes
import pathlib
import random
import string

import requests
import voluptuous as vol

from homeassistant.const import (
    CONF_PASSWORD, CONF_RECIPIENT, CONF_RESOURCE, CONF_ROOM, CONF_SENDER)
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.template as template_helper

from . import (
    ATTR_TITLE, ATTR_TITLE_DEFAULT, PLATFORM_SCHEMA, BaseNotificationService)

REQUIREMENTS = ['slixmpp==1.4.2']

_LOGGER = logging.getLogger(__name__)

ATTR_DATA = 'data'
ATTR_PATH = 'path'
ATTR_PATH_TEMPLATE = 'path_template'
ATTR_TIMEOUT = 'timeout'
ATTR_URL = 'url'
ATTR_URL_TEMPLATE = 'url_template'
ATTR_VERIFY = 'verify'

CONF_TLS = 'tls'
CONF_VERIFY = 'verify'

DEFAULT_CONTENT_TYPE = 'application/octet-stream'
DEFAULT_RESOURCE = 'home-assistant'
XEP_0363_TIMEOUT = 10

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SENDER): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_RECIPIENT): cv.string,
    vol.Optional(CONF_RESOURCE, default=DEFAULT_RESOURCE): cv.string,
    vol.Optional(CONF_ROOM, default=''): cv.string,
    vol.Optional(CONF_TLS, default=True): cv.boolean,
    vol.Optional(CONF_VERIFY, default=True): cv.boolean,
})


async def async_get_service(hass, config, discovery_info=None):
    """Get the Jabber (XMPP) notification service."""
    return XmppNotificationService(
        config.get(CONF_SENDER), config.get(CONF_RESOURCE),
        config.get(CONF_PASSWORD), config.get(CONF_RECIPIENT),
        config.get(CONF_TLS), config.get(CONF_VERIFY),
        config.get(CONF_ROOM), hass)


class XmppNotificationService(BaseNotificationService):
    """Implement the notification service for Jabber (XMPP)."""

    def __init__(self, sender, resource, password,
                 recipient, tls, verify, room, hass):
        """Initialize the service."""
        self._hass = hass
        self._sender = sender
        self._resource = resource
        self._password = password
        self._recipient = recipient
        self._tls = tls
        self._verify = verify
        self._room = room

    async def async_send_message(self, message="", **kwargs):
        """Send a message to a user."""
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        text = '{}: {}'.format(title, message) if title else message
        data = kwargs.get(ATTR_DATA)
        timeout = data.get(ATTR_TIMEOUT, XEP_0363_TIMEOUT) if data else None

        await async_send_message(
            '{}/{}'.format(self._sender, self._resource),
            self._password, self._recipient, self._tls,
            self._verify, self._room, self._hass, text,
            timeout, data)


async def async_send_message(
        sender, password, recipient, use_tls, verify_certificate, room, hass,
        message, timeout=None, data=None):
    """Send a message over XMPP."""
    import slixmpp
    from slixmpp.exceptions import IqError, IqTimeout, XMPPError
    from slixmpp.xmlstream.xmlstream import NotConnectedError
    from slixmpp.plugins.xep_0363.http_upload import FileTooBig, \
        FileUploadError, UploadServiceNotFound

    class SendNotificationBot(slixmpp.ClientXMPP):
        """Service for sending Jabber (XMPP) messages."""

        def __init__(self):
            """Initialize the Jabber Bot."""
            super().__init__(sender, password)

            self.loop = hass.loop

            self.force_starttls = use_tls
            self.use_ipv6 = False
            self.add_event_handler(
                'failed_auth', self.disconnect_on_login_fail)
            self.add_event_handler('session_start', self.start)

            if room:
                self.register_plugin('xep_0045')  # MUC
            if not verify_certificate:
                self.add_event_handler('ssl_invalid_cert',
                                       self.discard_ssl_invalid_cert)
            if data:
                # Init XEPs for image sending
                self.register_plugin('xep_0030')  # OOB dep
                self.register_plugin('xep_0066')  # Out of Band Data
                self.register_plugin('xep_0071')  # XHTML IM
                self.register_plugin('xep_0128')  # Service Discovery
                self.register_plugin('xep_0363')  # HTTP upload

            self.connect(force_starttls=self.force_starttls, use_ssl=False)

        async def start(self, event):
            """Start the communication and sends the message."""
            # Sending image and message independently from each other
            if data:
                await self.send_file(timeout=timeout)
            if message:
                self.send_text_message()

            self.disconnect(wait=True)

        async def send_file(self, timeout=None):
            """Send file via XMPP.

            Send XMPP file message using OOB (XEP_0066) and
            HTTP Upload (XEP_0363)
            """
            if room:
                self.plugin['xep_0045'].join_muc(room, sender, wait=True)

            try:
                # Uploading with XEP_0363
                _LOGGER.debug("Timeout set to %ss", timeout)
                url = await self.upload_file(timeout=timeout)

                _LOGGER.info("Upload success")
                if room:
                    _LOGGER.info("Sending file to %s", room)
                    message = self.Message(sto=room, stype='groupchat')
                else:
                    _LOGGER.info("Sending file to %s", recipient)
                    message = self.Message(sto=recipient, stype='chat')

                message['body'] = url
                # pylint: disable=invalid-sequence-index
                message['oob']['url'] = url
                try:
                    message.send()
                except (IqError, IqTimeout, XMPPError) as ex:
                    _LOGGER.error("Could not send image message %s", ex)
            except (IqError, IqTimeout, XMPPError) as ex:
                _LOGGER.error("Upload error, could not send message %s", ex)
            except NotConnectedError as ex:
                _LOGGER.error("Connection error %s", ex)
            except FileTooBig as ex:
                _LOGGER.error(
                    "File too big for server, could not upload file %s", ex)
            except UploadServiceNotFound as ex:
                _LOGGER.error("UploadServiceNotFound: "
                              " could not upload file %s", ex)
            except FileUploadError as ex:
                _LOGGER.error("FileUploadError, could not upload file %s", ex)
            except requests.exceptions.SSLError as ex:
                _LOGGER.error("Cannot establish SSL connection %s", ex)
            except requests.exceptions.ConnectionError as ex:
                _LOGGER.error("Cannot connect to server %s", ex)
            except (FileNotFoundError,
                    PermissionError,
                    IsADirectoryError,
                    TimeoutError) as ex:
                _LOGGER.error("Error reading file %s", ex)
            except FutTimeoutError as ex:
                _LOGGER.error("The server did not respond in time, %s", ex)

        async def upload_file(self, timeout=None):
            """Upload file to Jabber server and return new URL.

            upload a file with Jabber XEP_0363 from a remote URL or a local
            file path and return a URL of that file.
            """
            if data.get(ATTR_URL_TEMPLATE):
                _LOGGER.debug(
                    "Got url template: %s", data[ATTR_URL_TEMPLATE])
                templ = template_helper.Template(
                    data[ATTR_URL_TEMPLATE], hass)
                get_url = template_helper.render_complex(templ, None)
                url = await self.upload_file_from_url(
                    get_url, timeout=timeout)
            elif data.get(ATTR_URL):
                url = await self.upload_file_from_url(
                    data[ATTR_URL], timeout=timeout)
            elif data.get(ATTR_PATH_TEMPLATE):
                _LOGGER.debug(
                    "Got path template: %s", data[ATTR_PATH_TEMPLATE])
                templ = template_helper.Template(
                    data[ATTR_PATH_TEMPLATE], hass)
                get_path = template_helper.render_complex(templ, None)
                url = await self.upload_file_from_path(
                    get_path, timeout=timeout)
            elif data.get(ATTR_PATH):
                url = await self.upload_file_from_path(
                    data[ATTR_PATH], timeout=timeout)
            else:
                url = None

            if url is None:
                _LOGGER.error("No path or URL found for file")
                raise FileUploadError("Could not upload file")

            return url

        async def upload_file_from_url(self, url, timeout=None):
            """Upload a file from a URL. Returns a URL.

            uploaded via XEP_0363 and HTTP and returns the resulting URL
            """
            _LOGGER.info("Getting file from %s", url)

            def get_url(url):
                """Return result for GET request to url."""
                return requests.get(
                    url, verify=data.get(ATTR_VERIFY, True), timeout=timeout)
            result = await hass.async_add_executor_job(get_url, url)

            if result.status_code >= 400:
                _LOGGER.error("Could not load file from %s", url)
                return None

            filesize = len(result.content)

            # we need a file extension, the upload server needs a
            # filename, if none is provided, through the path we guess
            # the extension
            # also setting random filename for privacy
            if data.get(ATTR_PATH):
                # using given path as base for new filename. Don't guess type
                filename = self.get_random_filename(data.get(ATTR_PATH))
            else:
                extension = mimetypes.guess_extension(
                    result.headers['Content-Type']) or ".unknown"
                _LOGGER.debug("Got %s extension", extension)
                filename = self.get_random_filename(None, extension=extension)

            _LOGGER.info("Uploading file from URL, %s", filename)

            url = await self['xep_0363'].upload_file(
                filename, size=filesize, input_file=result.content,
                content_type=result.headers['Content-Type'], timeout=timeout)

            return url

        async def upload_file_from_path(self, path, timeout=None):
            """Upload a file from a local file path via XEP_0363."""
            _LOGGER.info('Uploading file from path, %s ...', path)

            if not hass.config.is_allowed_path(path):
                raise PermissionError(
                    "Could not access file. Not in whitelist.")

            with open(path, 'rb') as upfile:
                _LOGGER.debug("Reading file %s", path)
                input_file = upfile.read()
            filesize = len(input_file)
            _LOGGER.debug("Filesize is %s bytes", filesize)

            content_type = mimetypes.guess_type(path)[0]
            if content_type is None:
                content_type = DEFAULT_CONTENT_TYPE
            _LOGGER.debug("Content type is %s", content_type)

            # set random filename for privacy
            filename = self.get_random_filename(data.get(ATTR_PATH))
            _LOGGER.debug("Uploading file with random filename %s", filename)

            url = await self['xep_0363'].upload_file(
                filename, size=filesize, input_file=input_file,
                content_type=content_type, timeout=timeout)

            return url

        def send_text_message(self):
            """Send a text only message to a room or a recipient."""
            try:
                if room:
                    _LOGGER.debug("Joining room %s", room)
                    self.plugin['xep_0045'].join_muc(room, sender, wait=True)
                    self.send_message(
                        mto=room, mbody=message, mtype='groupchat')
                else:
                    _LOGGER.debug("Sending message to %s", recipient)
                    self.send_message(
                        mto=recipient, mbody=message, mtype='chat')
            except (IqError, IqTimeout, XMPPError) as ex:
                _LOGGER.error("Could not send text message %s", ex)
            except NotConnectedError as ex:
                _LOGGER.error("Connection error %s", ex)

        # pylint: disable=no-self-use
        def get_random_filename(self, filename, extension=None):
            """Return a random filename, leaving the extension intact."""
            if extension is None:
                path = pathlib.Path(filename)
                if path.suffix:
                    extension = ''.join(path.suffixes)
                else:
                    extension = ".txt"
            return ''.join(random.choice(string.ascii_letters)
                           for i in range(10)) + extension

        def disconnect_on_login_fail(self, event):
            """Disconnect from the server if credentials are invalid."""
            _LOGGER.warning("Login failed")
            self.disconnect()

        @staticmethod
        def discard_ssl_invalid_cert(event):
            """Do nothing if ssl certificate is invalid."""
            _LOGGER.info("Ignoring invalid SSL certificate as requested")

    SendNotificationBot()
