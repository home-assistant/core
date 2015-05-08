"""
Support for D-Link IP Cameras.
"""

import logging
import requests
import os
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers import validate_config
from homeassistant.components.camera import DOMAIN
from homeassistant.components.camera import Camera
from homeassistant.loader import get_component
# pylint: disable=import-error
from bs4 import BeautifulSoup

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return Vera lights. """
    if not validate_config({DOMAIN: config},
                       {DOMAIN: ['base_url', CONF_USERNAME, CONF_PASSWORD]},
                       _LOGGER):
        return None

    model_map = {
        'dcs-930l' : DlinkCameraDcs930l
    }

    family_map = {
        'dcs' : DlinkCameraDcs930l
    }

    # To load up the camera component we first check if there is component
    # for the specific model if not we then check the specified family,
    # if that also fails we just load the generic comonent for this brand.

    camera_class = DlinkCamera
    model = config.get('model', False)
    if model:
        model = model.lower()
        camera_class = model_map.get(model, DlinkCamera)

    family = config.get('family', False)
    if family and camera_class == DlinkCamera:
        family = family.lower()
        camera_class = family_map.get(family, DlinkCamera)


    camera = camera_class(hass, config)
    cameras = [camera]

    add_devices_callback(cameras)


# pylint: disable=too-many-public-methods
class DlinkCamera(Camera):
    """ A generic D-Link camera class """
    def __init__(self, hass, device_info):
        """ Initialise the generic D-Link camera class. """
        # pylint: disable=missing-super-argument
        super().__init__(hass, device_info)
        self._still_image_url = device_info.get('still_image_url', 'image.jpg')


# pylint: disable=too-many-public-methods
# pylint: disable=too-many-instance-attributes
class DlinkCameraDcs930l(Camera):
    """ A class designed for the D-Link DCS-930L, it may also work with other
    related devices """
    def __init__(self, hass, device_info):
        """ Initialise the D-Link DCS-930L camera component. """
        # pylint: disable=missing-super-argument
        super().__init__(hass, device_info)
        self._is_motion_detection_supported = True
        self._is_ftp_upload_supported = True
        self._still_image_url = device_info.get('still_image_url', 'image.jpg')

        # Holds the form data so we can post updates back to the web UI
        self._web_ui_form_data = {}
        self.get_all_settings()


    def refesh_all_settings_from_device(self):
        """ Overrides the base class method that retrieved all setting
            from the device. """
        self.get_all_settings()


    def get_all_settings(self):
        """ Pull all the settings from the camera, there is no API so it's
        dirty screen scraping time. """
        res = requests.get(self.base_url + 'motion.htm',
            auth=(self.username, self.password))
        motion_settings = BeautifulSoup(res.content)


        settings = self.extract_form_fields(motion_settings)
        self._is_motion_detection_enabled = (
            True if
            settings.get('MotionDetectionEnable') == '1' else
            False)

        self._web_ui_form_data['motion'] = settings

        # This is pretty lame, for some reason the motion detection area is
        # returned like this instead on in the same way as the other or
        # even JSON
        res = requests.get(self.base_url + 'motion.cgi',
            auth=(self.username, self.password))

        lines = res.text.splitlines(True)

        for line in lines:
            line = line.strip()
            keypair = line.split("=")
            if len(keypair) > 1:
                self._web_ui_form_data['motion'][keypair[0]] = keypair[1]

        res = requests.get(self.base_url + 'upload.htm',
            auth=(self.username, self.password))

        upload_settings = BeautifulSoup(res.content)

        u_settings = self.extract_form_fields(upload_settings)
        self._is_ftp_upload_enabled = (True if
            u_settings.get('FTPScheduleEnable') == '1' else
            False)

        self._web_ui_form_data['upload'] = u_settings

        self._is_ftp_configured = (True if not
            u_settings.get('FTPHostAddress') == '' else
            False)
        self._ftp_host = u_settings.get('FTPHostAddress')
        self._ftp_port = u_settings.get('FTPPortNumber')
        self._ftp_username = u_settings.get('FTPUserName')
        self._ftp_password = u_settings.get('FTPPassword')

        ftp_comp = get_component('ftp')
        if ftp_comp != None and ftp_comp.FTP_SERVER != None:
            self._ftp_path = os.path.join(
                ftp_comp.FTP_SERVER.ftp_root_path,
                u_settings.get('FTPDirectoryPath',
                self.entity_id))


    def enable_motion_detection(self):
        """ Enable the motion detection settings for the camera. """
        # pylint: disable=missing-super-argument
        can_enable = super().enable_motion_detection()
        if can_enable == False:
            return can_enable

        self._web_ui_form_data['motion']['MotionDetectionEnable'] = 1
        self._web_ui_form_data['motion']['MotionDetectionScheduleMode'] = 0
        # The camera won't detect any motion if there are no blocks set
        # so we default them to all set if none are selected
        if (self._web_ui_form_data['motion']['MotionDetectionBlockSet'] ==
            '0000000000000000000000000'):
            self._web_ui_form_data['motion']['MotionDetectionBlockSet'] = (
                '1111111111111111111111111')
        requests.post(self.base_url + 'setSystemMotion',
            data=self._web_ui_form_data['motion'],
            auth=(self.username,
            self.password))

        # self._is_motion_detection_enabled = False
        self.refesh_all_settings_from_device()
        self.update_ha_state(True)

        return True

    def disable_motion_detection(self):
        """ Disable the motion detection settings for the camera. """
        # pylint: disable=missing-super-argument
        can_enable = super().disable_motion_detection()
        if can_enable == False:
            return can_enable

        self._web_ui_form_data['motion']['MotionDetectionEnable'] = 0
        requests.post(self.base_url + 'setSystemMotion',
                                        data=self._web_ui_form_data['motion'],
                                        auth=(self.username, self.password))

        self.refesh_all_settings_from_device()
        self.update_ha_state(True)
        # self._is_motion_detection_enabled = False
        return True

    def set_ftp_details(self):
        """ Sets the FTP details used by the camera to upload motion
            detected images.  The details will be set to the appropriate
            values from the loaded ftp component """
        # pylint: disable=missing-super-argument
        can_enable = super().set_ftp_details()
        if can_enable == False:
            return can_enable

        ftp_server = get_component('ftp').FTP_SERVER

        ftp_path = self.ftp_path

        if not os.path.isdir(ftp_path):
            os.makedirs(ftp_path)
            _LOGGER.info(
                'Camera {0} image path did not exist and was \
                atomatically created at {1}'
                .format(self.entity_id, ftp_path))

        self._web_ui_form_data['upload']['FTPHostAddress'] = (
            ftp_server.server_ip)
        self._web_ui_form_data['upload']['FTPPortNumber'] = (
            ftp_server.server_port)
        self._web_ui_form_data['upload']['FTPUserName'] = (
            ftp_server.username)
        self._web_ui_form_data['upload']['FTPPassword'] = (
            ftp_server.password)
        self._web_ui_form_data['upload']['FTPDirectoryPath'] = (
            self.entity_id)

        self._web_ui_form_data['upload']['FTPScheduleEnable'] = '1'
        self._web_ui_form_data['upload']['FTPScheduleMode'] = '2'

        requests.post(self.base_url + 'setSystemFTP',
            data=self._web_ui_form_data['upload'],
            auth=(self.username, self.password))

        self.refesh_all_settings_from_device()
        self.update_ha_state(True)

        return True


    # From https://gist.github.com/simonw/104413
    # pylint: disable=too-many-branches
    # pylint: disable=no-self-use
    def extract_form_fields(self, soup, include_without_name=False):
        "Turn a BeautifulSoup form in to a dict of fields and default values"
        fields = {}
        for html_input in soup.findAll('input'):
            name = ''
            # ignore submit/image with no name attribute
            if (html_input['type'] in ('submit', 'image') and not
                html_input.has_attr('name')):
                continue

            if html_input == None:
                continue

            if (not html_input.has_attr('name') and not
                html_input.has_attr('id')):
                continue

            if (not html_input.has_attr('name') and
                html_input.has_attr('id') and
                include_without_name):

                name = html_input['id']
            elif html_input.has_attr('name'):
                name = html_input['name']
            else:
                continue

            # single element nome/value fields
            if html_input['type'] in (
                'text', 'hidden', 'password', 'submit', 'image'):

                value = ''
                if html_input.has_attr('value'):
                    value = html_input['value']
                fields[name] = value
                continue

            # checkboxes and radios
            if html_input['type'] in ('checkbox', 'radio'):
                value = ''
                if html_input.has_attr('checked'):
                    if html_input.has_attr('value'):
                        value = html_input['value']
                    else:
                        value = 'on'
                if name in fields.keys() and value:
                    fields[name] = value

                if not name in fields.keys():
                    fields[name] = value

                continue

        # textareas
        for textarea in soup.findAll('textarea'):
            fields[name] = textarea.string or ''

        # select fields
        for select in soup.findAll('select'):
            if not select.has_attr('name'):
                continue
            value = ''
            options = select.findAll('option')
            is_multiple = select.has_attr('multiple')

            selected_options = [
                option for option in options
                if option.has_attr('selected')
            ]

            # If no select options, go with the first one
            if not selected_options and options:
                selected_options = [options[0]]

            if not is_multiple:
                assert len(selected_options) < 2
                if len(selected_options) == 1:
                    value = (
                        selected_options[0].text if not
                        selected_options[0].has_attr('value') else
                        selected_options[0]['value'])
            else:
                value = (
                    [option.text if not
                    option.has_attr('value') else
                    option['value'] for option in selected_options])

            fields[select['name']] = value

        return fields
