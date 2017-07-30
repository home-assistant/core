"""HTTP utilities."""
from ipaddress import ip_address

from .const import (
    KEY_REAL_IP, KEY_USE_X_FORWARDED_FOR, HTTP_HEADER_X_FORWARDED_FOR)


def get_real_ip(request):
    """Get IP address of client."""
    if KEY_REAL_IP in request:
        return request[KEY_REAL_IP]

    if (request.app[KEY_USE_X_FORWARDED_FOR] and
            HTTP_HEADER_X_FORWARDED_FOR in request.headers):
        request[KEY_REAL_IP] = ip_address(
            request.headers.get(HTTP_HEADER_X_FORWARDED_FOR).split(',')[0])
    else:
        peername = request.transport.get_extra_info('peername')

        if peername:
            request[KEY_REAL_IP] = ip_address(peername[0])
        else:
            request[KEY_REAL_IP] = None

    return request[KEY_REAL_IP]
