"""Helpers for Agent DVR component."""
from .const import DOMAIN as AGENT_DOMAIN


def service_signal(service, ident=None):
    """Encode service and identifier into signal."""
    signal = f"{AGENT_DOMAIN}_{service}"
    if ident:
        signal += "_{}".format(ident.replace(".", "_"))
    return signal


def generate_url(host, port) -> str:
    """Create a URL from the host and port."""
    server_origin = host
    if "://" not in host:
        server_origin = f"http://{host}"

    if server_origin[-1] == "/":
        server_origin = server_origin[:-1]

    return f"{server_origin}:{port}/"
