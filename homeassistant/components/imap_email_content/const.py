"""Constants for the imap email content integration."""

from homeassistant.util.ssl import SSLCipherList

DOMAIN = "imap_email_content"

CONF_SERVER = "server"
CONF_SENDERS = "senders"
CONF_FOLDER = "folder"
CONF_SSL_CIPHER_LIST = "ssl_cipher_list"

ATTR_FROM = "from"
ATTR_BODY = "body"
ATTR_SUBJECT = "subject"

DEFAULT_PORT = 993
DEFAULT_SSL_CIPHER_LIST = SSLCipherList.PYTHON_DEFAULT
