"""Helpers for Agent DVR component."""


def generate_url(host, port) -> str:
    """Create a URL from the host and port."""
    server_origin = host
    if "://" not in host:
        server_origin = f"http://{host}"

    if server_origin[-1] == "/":
        server_origin = server_origin[:-1]

    return f"{server_origin}:{port}/"
