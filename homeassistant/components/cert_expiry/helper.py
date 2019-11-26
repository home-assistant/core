"""Helper functions for the Cert Expiry platform."""
import socket
import ssl

from .const import TIMEOUT


def get_cert(host, port):
    """Get the ssl certificate for the host and port combination."""
    ctx = ssl.create_default_context()
    address = (host, port)
    with socket.create_connection(address, timeout=TIMEOUT) as sock:
        with ctx.wrap_socket(sock, server_hostname=address[0]) as ssock:
            # pylint disable: https://github.com/PyCQA/pylint/issues/3166
            cert = ssock.getpeercert()  # pylint: disable=no-member
            return cert
