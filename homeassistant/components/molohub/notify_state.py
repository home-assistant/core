"""UI class for Molohub."""
import html
import urllib.parse

from .const import (BIND_AUTH_STR_TEMPLATE_DEFAULT, OPENTYPE_COUNT_DEFAULT,
                    SERVER_CONNECTING_STR_TEMPLATE_DEFAULT, STAGE_AUTH_BINDED,
                    STAGE_SERVER_CONNECTED, STAGE_SERVER_UNCONNECTED,
                    WAIT_FOR_AUTH_STR_TEMPLATE_DEFAULT)
from .utils import LOGGER


class NotifyState:
    """UI class for Molohub."""

    molo_server_host_str = ''

    server_connecting_str_template = SERVER_CONNECTING_STR_TEMPLATE_DEFAULT
    wait_for_auth_str_template = WAIT_FOR_AUTH_STR_TEMPLATE_DEFAULT
    bind_auth_str_template = BIND_AUTH_STR_TEMPLATE_DEFAULT
    opentype_count = OPENTYPE_COUNT_DEFAULT

    cur_notify_str = server_connecting_str_template
    cur_stage = STAGE_SERVER_UNCONNECTED
    cur_data = None

    OPENTYPE_LOGO = {
        'default': '''<img src="/" hegiht="32px" alt="icon_error"/>'''
    }

    def update_state(self, data):
        """Update UI state."""
        stage = data.get('stage')

        # STAGE_AUTH_BINDED possible update
        if self.cur_stage == stage and self.cur_stage != STAGE_AUTH_BINDED:
            LOGGER.debug("Stage not changed. ignore update %s ", stage)
            return

        if stage:
            self.cur_stage = stage
            self.cur_data = data

        # Update part of values.
        for item in data:
            if item in self.update_func_bind_map:
                self.update_func_bind_map[item](self, data)

        LOGGER.debug("cur_data %s", str(self.cur_data))

        # On stage change.
        if self.cur_stage in self.on_stage_func_bind_map:
            self.on_stage_func_bind_map[self.cur_stage](self, data)

    def get_notify_str(self):
        """Get current UI state."""
        return self.cur_notify_str

    def update_token(self, data):
        """Handle update token."""
        data_copy = data.copy()
        data_copy.pop('update_token', None)
        self.cur_data.update(data_copy)
        LOGGER.debug('update_token %s', str(data_copy))

    def update_ui(self, data):
        """Handle update UI templetes."""
        self.OPENTYPE_LOGO.update(data['platform_icon'])
        self.opentype_count = len(data['platform_icon'])
        self.server_connecting_str_template = data['uncnn_templ']
        self.bind_auth_str_template = data['cnn_templ']
        self.wait_for_auth_str_template = data['link_templ']
        LOGGER.debug('update_ui %s', str(data))

    update_func_bind_map = {
        'update_token': update_token,
        'update_ui': update_ui
    }

    def on_stage_server_unconnected(self, data):
        """Handle hass event: on_stage_server_unconnected."""
        LOGGER.info("server offline")
        self.cur_notify_str = self.server_connecting_str_template

    def on_stage_serverconnected(self, data):
        """Handle hass event: on_stage_serverconnected."""
        LOGGER.info("server online, wait for bind")
        token = urllib.parse.quote(self.cur_data.get('token'))
        token_list = []
        i = 0
        while i < self.opentype_count:
            token_list.append(self.molo_server_host_str)
            token_list.append(token)
            i += 1
        self.cur_notify_str = (
            self.wait_for_auth_str_template % tuple(token_list))
        LOGGER.debug("Update nofiy str token %s", token)

    def on_stage_auth_binded(self, data):
        """Handle hass event: on_stage_auth_binded."""
        LOGGER.info("server online, successfully bind")
        token = urllib.parse.quote(self.cur_data.get('token'))
        opentype = self.cur_data.get('opentype')
        openid = self.cur_data.get('openid')
        uname = self.cur_data.get('uname')
        uname = html.escape(uname)
        upicture = self.cur_data.get('upicture')
        LOGGER.debug("Update nofiy str opentype: %s, openid: %s, token: %s",
                     opentype, openid, token)
        if opentype not in self.OPENTYPE_LOGO:
            opentype = 'default'
        self.cur_notify_str = (self.bind_auth_str_template % (
            self.OPENTYPE_LOGO[opentype] % (self.molo_server_host_str),
            upicture, uname, self.molo_server_host_str, token))

    on_stage_func_bind_map = {
        STAGE_SERVER_UNCONNECTED: on_stage_server_unconnected,
        STAGE_SERVER_CONNECTED: on_stage_serverconnected,
        STAGE_AUTH_BINDED: on_stage_auth_binded
    }
