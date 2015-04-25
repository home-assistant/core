import logging
import requests
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers import validate_config
from homeassistant.components.camera import DOMAIN
from homeassistant.components.camera import Camera
from bs4 import BeautifulSoup

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return Vera lights. """
    try:
        if not validate_config({DOMAIN: config},
                           {DOMAIN: ['base_url', CONF_USERNAME, CONF_PASSWORD]},
                           _LOGGER):
            return None

        cameras = [DlinkCamera(hass, config)]

        add_devices_callback(cameras)
    except Exception as inst:
        _LOGGER.error("Could not find cameras: %s", inst)
        return False

def get_camera(hass, device_info):
    return DlinkCamera(hass, device_info)


# class DlinkCamera(Camera):
#     def __init__(self, hass, device_info):
#         super().__init__(hass, device_info)

#     @property
#     def still_image_url(self):
#         """ This should be implemented by different camera models. """
#         return self.BASE_URL + 'image.jpg'

class DlinkCamera(Camera):
    def __init__(self, hass, device_info):
        super().__init__(hass, device_info)
        self._is_motion_detection_supported = True
        self._is_ftp_upload_supported = True

        # Holds the form data so we can post updates back to the web UI
        self._web_ui_form_data = {}
        self.get_all_settings()

    @property
    def still_image_url(self):
        """ This should be implemented by different camera models. """
        return self.BASE_URL + 'image.jpg'

    def get_all_settings(self):
        res = requests.get(self.BASE_URL + 'motion.htm', auth=(self.username, self.password))
        motion_settings = BeautifulSoup(res.content)

        print('----------------------------------------------------------------------------------')
        settings = self.extract_form_fields(motion_settings)
        self._is_motion_detection_enabled = True if settings.get('MotionDetectionEnable') == '1' else False
        print(settings)
        self._web_ui_form_data['motion'] = settings

        print('motion detection ' + str(self._is_motion_detection_enabled))

        res = requests.get(self.BASE_URL + 'upload.htm', auth=(self.username, self.password))
        upload_settings = BeautifulSoup(res.content)

        u_settings = self.extract_form_fields(upload_settings)
        self._is_ftp_upload_enabled = True if u_settings.get('FTPScheduleEnable') == '1' else False

        print(self._is_ftp_upload_enabled)

        print(u_settings)

        self._web_ui_form_data['upload'] = u_settings

        self._is_ftp_configured = True if not u_settings.get('FTPHostAddress') == '' else False
        self._ftp_host = u_settings.get('FTPHostAddress')
        self._ftp_port = u_settings.get('FTPPortNumber')
        self._ftp_username = u_settings.get('FTPUserName')
        self._ftp_password = u_settings.get('FTPPassword')

        print(self._is_ftp_configured)
        print(self.get_ha_lan_address())

    def enable_motion_detection(self):
        can_enable = super().enable_motion_detection()
        if can_enable == False:
            return can_enable

        self._web_ui_form_data['motion']['MotionDetectionEnable'] = 1
        self._web_ui_form_data['motion']['MotionDetectionScheduleMode'] = 0
        r = requests.post(self.BASE_URL + 'setSystemMotion', data=self._web_ui_form_data['motion'], auth=(self.username, self.password))

        self.get_all_settings()
        self.update_ha_state(True)

        return True

    def disable_motion_detection(self):
        can_enable = super().disable_motion_detection()
        if can_enable == False:
            return can_enable

        self._web_ui_form_data['motion']['MotionDetectionEnable'] = 0
        r = requests.post(self.BASE_URL + 'setSystemMotion', data=self._web_ui_form_data['motion'], auth=(self.username, self.password))

        self.get_all_settings()
        self.update_ha_state(True)

        return True

    def set_ftp_details(self):
        can_enable = super().set_ftp_details()
        if can_enable == False:
            return can_enable

        self._web_ui_form_data['upload']['FTPHostAddress'] = self.get_ha_lan_address()
        self._web_ui_form_data['upload']['FTPPortNumber'] = 21
        self._web_ui_form_data['upload']['FTPUserName'] = 'test'
        self._web_ui_form_data['upload']['FTPPassword'] = 'test'
        self._web_ui_form_data['upload']['FTPDirectoryPath'] = '/'

        self._web_ui_form_data['upload']['FTPScheduleEnable'] = '1'
        self._web_ui_form_data['upload']['FTPScheduleMode'] = '2'

        r = requests.post(self.BASE_URL + 'setSystemFTP', data=self._web_ui_form_data['upload'], auth=(self.username, self.password))

        print(r.content)

        self.get_all_settings()
        self.update_ha_state(True)

        return True


    # From https://gist.github.com/simonw/104413
    def extract_form_fields(self, soup, include_without_name=False):
        "Turn a BeautifulSoup form in to a dict of fields and default values"
        fields = {}
        for input in soup.findAll('input'):
            name = ''
            # ignore submit/image with no name attribute
            if input['type'] in ('submit', 'image') and not input.has_attr('name'):
                continue

            # print(input)
            if input == None:
                continue

            if not input.has_attr('name') and not input.has_attr('id'):
                continue

            if not input.has_attr('name') and input.has_attr('id') and include_without_name:
                name = input['id']
            elif input.has_attr('name'):
                name = input['name']
            else:
                continue



            # single element nome/value fields
            if input['type'] in ('text', 'hidden', 'password', 'submit', 'image'):
                value = ''
                if input.has_attr('value'):
                    value = input['value']
                fields[name] = value
                continue

            # checkboxes and radios
            if input['type'] in ('checkbox', 'radio'):
                value = ''
                if input.has_attr('checked'):
                    if input.has_attr('value'):
                        value = input['value']
                    else:
                        value = 'on'
                if name in fields.keys() and value:
                    fields[name] = value

                if not name in fields.keys():
                    fields[name] = value

                continue

            # assert False, 'input type %s not supported' % input['type']

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
                assert(len(selected_options) < 2)
                if len(selected_options) == 1:
                    value = selected_options[0].text if not selected_options[0].has_attr('value') else selected_options[0]['value']
            else:
                value = [option.text if not option.has_attr('value') else option['value'] for option in selected_options]

            fields[select['name']] = value

        return fields