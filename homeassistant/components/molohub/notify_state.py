"""UI class for Molohub."""
import html
import urllib.parse

from .const import (BIND_AUTH_STR_TEMPLATE_DEFAULT,
                    SERVER_CONNECTING_STR_TEMPLATE_DEFAULT, STAGE_AUTH_BINDED,
                    STAGE_SERVER_CONNECTED, STAGE_SERVER_UNCONNECTED,
                    WAIT_FOR_AUTH_STR_TEMPLATE_DEFAULT)
from .utils import LOGGER, fire_molohub_event


class NotifyState:
    """UI class for Molohub."""

    ha_context = None
    molo_server_host_str = ''

    cur_notify_str = SERVER_CONNECTING_STR_TEMPLATE_DEFAULT
    cur_data = {
        'stage': STAGE_SERVER_UNCONNECTED,
        'uncnn_templ': SERVER_CONNECTING_STR_TEMPLATE_DEFAULT,
        'cnn_templ': BIND_AUTH_STR_TEMPLATE_DEFAULT,
        'link_templ': WAIT_FOR_AUTH_STR_TEMPLATE_DEFAULT,
        'platform_icon': {
            'default': '''<img src="/" hegiht="32px" alt="icon_error"/>'''
        }
    }

    generate_str_func_bind_map = {}

    def __init__(self):
        """Initialize NotifyState class."""
        self.init_func_bind_map()

    def set_context(self, hass, host_str):
        """Set HA context and server host string."""
        self.ha_context = hass
        self.molo_server_host_str = host_str

    def update_state(self, data):
        """Update UI state."""
        last_stage = self.cur_data.get('stage')
        last_notify_str = self.get_notify_str()

        # Update data
        self.cur_data.update(data)
        cur_stage = self.cur_data.get('stage')
        LOGGER.debug("cur_data %s", str(self.cur_data))

        # Generate notify string according to stage
        if cur_stage in self.generate_str_func_bind_map:
            self.generate_str_func_bind_map[cur_stage]()

        # If notify string changed, inform UI to update
        if last_notify_str == self.get_notify_str():
            return

        # If stage changed, log new stage
        if cur_stage != last_stage:
            LOGGER.info(self.state_log_str[cur_stage])

        # Inform UI to update
        fire_molohub_event(self.ha_context, None)

    def get_notify_str(self):
        """Get current UI state."""
        return self.cur_notify_str

    def generate_str_server_unconnected(self):
        """Handle hass event: on_stage_server_unconnected."""
        self.cur_notify_str = self.cur_data.get('uncnn_templ')

    def generate_str_serverconnected(self):
        """Handle hass event: on_stage_serverconnected."""
        token = urllib.parse.quote(self.cur_data.get('token'))
        token_list = []
        opentype_count = len(self.cur_data.get('platform_icon'))
        i = 0
        while i < opentype_count:
            token_list.append(self.molo_server_host_str)
            token_list.append(token)
            i += 1
        self.cur_notify_str = (
            self.cur_data.get('link_templ') % tuple(token_list))
        LOGGER.debug("Update nofiy str token %s", token)

    def generate_str_auth_binded(self):
        """Handle hass event: on_stage_auth_binded."""
        token = urllib.parse.quote(self.cur_data.get('token'))
        opentype = self.cur_data.get('opentype')
        openid = self.cur_data.get('openid')
        uname = self.cur_data.get('uname')
        uname = html.escape(uname)
        upicture = self.cur_data.get('upicture')
        LOGGER.debug("Update nofiy str opentype: %s, openid: %s, token: %s",
                     opentype, openid, token)
        if opentype not in self.cur_data.get('platform_icon'):
            opentype = 'default'
        self.cur_notify_str = (self.cur_data.get('cnn_templ') %
                               (self.cur_data.get('platform_icon')[opentype] %
                                (self.molo_server_host_str), upicture, uname,
                                self.molo_server_host_str, token))

    def init_func_bind_map(self):
        """Initialize function bind map and state log string map."""
        self.generate_str_func_bind_map = {
            STAGE_SERVER_UNCONNECTED: self.generate_str_server_unconnected,
            STAGE_SERVER_CONNECTED: self.generate_str_serverconnected,
            STAGE_AUTH_BINDED: self.generate_str_auth_binded
        }
        self.state_log_str = {
            STAGE_SERVER_UNCONNECTED: 'server offline',
            STAGE_SERVER_CONNECTED: 'server online, wait for authorize',
            STAGE_AUTH_BINDED: 'server online, successfully authorized'
        }


NOTIFY_STATE = NotifyState()
