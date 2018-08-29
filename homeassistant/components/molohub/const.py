"""Constants for Molohub."""

BIND_AUTH_STR_TEMPLATE_DEFAULT = """
<table align="center" width="100%%">
<tr>
    <td width="10%%" align="center">
        %s
    </td>
    <td width="30%%" align="right">
        <img src="%s" width="32px" hegiht="32px"/>
    </td>
    <td width="40%%" align="left">%s</td>
    <td width="20%%" align="center">
        <a href="http://%s/unbind?token=%s">Disconnect</a>
    </td>
</tr>
</table>
""".strip().replace('>\n', '>')

BUFFER_SIZE = 1024

CLIENT_VERSION = '0.12'
CONNECTED = 1

HTTP_502_BODY = """
<html><body style="background-color: #97a8b9">
<div style="
    margin:auto;
    width:400px;
    padding: 20px 60px;
    background-color: #D3D3D3;
    border: 5px solid maroon;">
<h2>Tunnel %s unavailable</h2>
<p>Unable to initiate connection to <strong>%s</strong>.
This port is not yet available for web server.</p>
"""

HTTP_502_HEADER = """
HTTP/1.0 502 Bad Gateway\r
Content-Type: text/html\r
Content-Length: %d\r\n\r\n%s
"""

PING_INTERVAL_DEFAULT = 10

RECONNECT_INTERVAL = 5

SERVER_CONNECTING_STR_TEMPLATE_DEFAULT = "Connecting server..."
STAGE_SERVER_UNCONNECTED = 'server_unconnected'
STAGE_SERVER_CONNECTED = 'server_connected'
STAGE_AUTH_BINDED = 'auth_binded'

TCP_PACK_HEADER_LEN = 16
TOKEN_KEY_NAME = 'slavertoken'

CLIENT_STATUS_UNBINDED = "unbinded"
CLIENT_STATUS_BINDED = "binded"

CONFIG_FILE_NAME = "molo_client_config.yaml"

WAIT_FOR_AUTH_STR_TEMPLATE_DEFAULT = """
Choose platform below to connect:

- [google](http://%s/login/google?token=%s)
"""

PROXY_TCP_CONNECTION_ACTIVATE_TIME = 60
