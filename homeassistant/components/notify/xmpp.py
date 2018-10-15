"""
Jabber (XMPP) notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.xmpp/
"""
import logging
import requests
# pylint: disable=redefined-builtin
from requests.exceptions import ConnectionError, SSLError
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.notify import (
    ATTR_TITLE, ATTR_TITLE_DEFAULT, PLATFORM_SCHEMA, BaseNotificationService)
from homeassistant.const import (
    CONF_PASSWORD, CONF_SENDER, CONF_RECIPIENT, CONF_ROOM, CONF_RESOURCE)

REQUIREMENTS = ['slixmpp==1.4.0']

_LOGGER = logging.getLogger(__name__)

CONF_TLS = 'tls'
CONF_VERIFY = 'verify'

ATTR_DATA = 'data'
ATTR_PATH = 'path'
ATTR_URL = 'url'
ATTR_VERIFY = 'verify'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SENDER): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_RECIPIENT): cv.string,
    vol.Optional(CONF_TLS, default=True): cv.boolean,
    vol.Optional(CONF_VERIFY, default=True): cv.boolean,
    vol.Optional(CONF_ROOM, default=''): cv.string,
    vol.Optional(CONF_RESOURCE, default="home-assistant"): cv.string,
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
        data = None or kwargs.get(ATTR_DATA)

        await async_send_message(
            '{}/{}'.format(self._sender, self._resource),
            self._password, self._recipient, self._tls,
            self._verify, self._room, self._hass, text, data)


async def async_send_message(sender, password, recipient, use_tls,
                             verify_certificate, room, hass, message,
                             data=None):
    """Send a message over XMPP."""
    import slixmpp
    from slixmpp.plugins.xep_0363.http_upload import FileTooBig, \
        FileUploadError, UploadServiceNotFound

    class SendNotificationBot(slixmpp.ClientXMPP):
        """Service for sending Jabber (XMPP) messages."""

        def __init__(self):
            """Initialize the Jabber Bot."""
            super().__init__(sender, password)

            # need hass.loop!!
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
                # init XEPs for image sending
                self.register_plugin('xep_0030')  # OOB dep
                self.register_plugin('xep_0066')  # Out of Band Data
                self.register_plugin('xep_0071')  # XHTML IM
                self.register_plugin('xep_0128')  # Service Discovery
                self.register_plugin('xep_0363')  # HTTP upload

            self.connect(force_starttls=self.force_starttls, use_ssl=False)

        async def start(self, event):
            """Start the communication and sends the message."""
            self.get_roster()
            self.send_presence()

            # sending image and message independently from each other
            if data:
                await self.send_image()
            if message:
                self.send_text_message()
            self.disconnect(wait=True)

        async def send_image(self):
            """Send image via XMPP.

            Send XMPP image message using OOB (XEP_0066) and
            HTTP Upload (XEP_0363)
            """
            if room:
                # self.plugin['xep_0045'].join_muc(room, sender, wait=True)
                # message = self.Message(sto=room, stype='groupchat')
                _LOGGER.error("sorry, sending images to rooms is"
                              " currently not supported")
                return

            try:
                url = await self.upload_file()  # uploading with XEP_0363
            except FileTooBig as ex:
                _LOGGER.error("File too big for server, "
                              "could not upload file %s", ex)
            except (UploadServiceNotFound,
                    FileUploadError) as ex:
                _LOGGER.error("could not upload file %s", ex)
            except SSLError as ex:
                _LOGGER.error("cannot establish SSL connection %s", ex)
            except ConnectionError as ex:
                _LOGGER.error("cannot connect to server %s", ex)
            else:
                _LOGGER.info("Upload success")

                _LOGGER.info('Sending file to %s', recipient)
                message = self.Message(sto=recipient, stype='chat')
                message['body'] = url
                # pylint: disable=invalid-sequence-index
                message['oob']['url'] = url
                message.send()

        async def upload_file(self):
            """Upload file to Jabber server and return new URL.

            upload a file with Jabber XEP_0363 from a remote URL or a local
            file path and return a URL of that file.
            """
            if data.get(ATTR_URL):
                # send a file from an URL
                url = data.get(ATTR_URL)
                _LOGGER.info('getting file from %s', url)

                # result = await loop.run_in_executor(None, requests.get, url)
                if data.get(ATTR_VERIFY, True):
                    # if True or not set
                    result = await hass.async_add_executor_job(requests.get,
                                                               url)
                else:
                    def get_insecure_url(url):
                        return requests.get(url, verify=False)
                    result = await hass.async_add_executor_job(
                        get_insecure_url, url)

                if result.status_code >= 400:
                    _LOGGER.error("could not load file from %s", url)
                    return

                length = len(result.content)
                # we need a file extension, the upload server needs a
                # filename, if none is provided, through the path
                # we guess the extension
                if not data.get(ATTR_PATH):
                    extension = self.get_extension(
                        result.headers['Content-Type'])
                    _LOGGER.debug("got %s extension", extension)
                filename = data.get(ATTR_PATH) if data.get(ATTR_PATH) \
                    else "upload"+extension
                url = await self['xep_0363'].upload_file(
                    filename,
                    # size=int(result.headers['Content-Length']),
                    size=length,
                    input_file=result.content,
                    content_type=result.headers['Content-Type'])
            elif data.get(ATTR_PATH):
                # send message from local path
                filename = data.get(ATTR_PATH) if data else None
                _LOGGER.info('Uploading file %s ...', filename)
                url = await self['xep_0363'].upload_file(filename)
            else:
                _LOGGER.error("no path or URL found for image")

            _LOGGER.info('Upload success!')
            return url

        def send_text_message(self):
            """Send a text only message to a room or a recipient."""
            if room:
                _LOGGER.debug("Joining room %s", room)
                self.plugin['xep_0045'].join_muc(room, sender, wait=True)
                self.send_message(mto=room, mbody=message, mtype='groupchat')
            else:
                _LOGGER.debug("message to %s", recipient)
                self.send_message(mto=recipient, mbody=message, mtype='chat')

        # pylint: disable=no-self-use
        def get_extension(self, content_type):
            # pylint: disable=line-too-long
            """Get a file extension based on a content type."""
            types = {'audio/aac': '.aac',
                     'application/x-abiword': '.abw',
                     'video/x-msvideo': '.avi',
                     'application/vnd.amazon.ebook': '.azw',
                     'application/octet-stream': '.bin',
                     'image/bmp': '.bmp',
                     'application/x-bzip': '.bz',
                     'application/x-bzip2': '.bz2',
                     'application/x-csh': '.csh',
                     'text/css': '.css',
                     'text/csv': '.csv',
                     'application/msword': '.doc',
                     'application/vnd.openxmlformats-officedocument'
                     '.wordprocessingml.document': '.docx',
                     'application/vnd.ms-fontobject': '.eot',
                     'application/epub+zip': '.epub',
                     'application/ecmascript': '.es',
                     'image/gif': '.gif',
                     'text/html': '.html',
                     'image/x-icon': '.ico',
                     'text/calendar': '.ics',
                     'application/java-archive': '.jar',
                     'image/jpeg': '.jpg',
                     'application/javascript': '.js',
                     'application/json': '.json',
                     'audio/midi': '.midi',
                     'audio/x-midi': '.midi',
                     'video/mpeg': '.mpeg',
                     'application/vnd.apple.installer+xml': '.mpkg',
                     'application/'
                     'vnd.oasis.opendocument.presentation': '.odp',
                     'application/vnd.oasis.opendocument.spreadsheet': '.ods',
                     'application/vnd.oasis.opendocument.text': '.odt',
                     'audio/ogg': '.oga',
                     'video/ogg': '.ogv',
                     'application/ogg': '.ogx',
                     'font/otf': '.otf',
                     'image/png': '.png',
                     'application/pdf': '.pdf',
                     'application/vnd.ms-powerpoint': '.ppt',
                     'application/vnd.openxmlformats-officedocument.'
                     'presentationml.presentation': '.pptx',
                     'application/x-rar-compressed': '.rar',
                     'application/rtf': '.rtf',
                     'application/x-sh': '.sh',
                     'image/svg+xml': '.svg',
                     'application/x-shockwave-flash': '.swf',
                     'application/x-tar': '.tar',
                     'image/tiff': '.tiff',
                     'application/typescript': '.ts',
                     'font/ttf': '.ttf',
                     'text/plain': '.txt',
                     'application/vnd.visio': '.vsd',
                     'audio/wav': '.wav',
                     'audio/webm': '.weba',
                     'video/webm': '.webm',
                     'image/webp': '.webp',
                     'font/woff': '.woff',
                     'font/woff2': '.woff2',
                     'application/xhtml+xml': '.xhtml',
                     'application/vnd.ms-excel': '.xls',
                     'application/vnd.openxmlformats-officedocument.'
                     'spreadsheetml.sheet': '.xlsx',
                     'application/xml': '.xml',
                     'application/vnd.mozilla.xul+xml': '.xul',
                     'application/zip': '.zip',
                     'video/3gpp': '.3gp',
                     'video/3gpp2': '.3g2',
                     'application/x-7z-compressed': '.7z',
                     }
            try:
                return types[content_type.lower()]
            except KeyError:
                _LOGGER.warning("unknown, can't upload unknown file type")

        def disconnect_on_login_fail(self, event):
            """Disconnect from the server if credentials are invalid."""
            _LOGGER.warning('Login failed')
            self.disconnect()

        @staticmethod
        def discard_ssl_invalid_cert(event):
            """Do nothing if ssl certificate is invalid."""
            _LOGGER.info('Ignoring invalid ssl certificate as requested')

    SendNotificationBot()
