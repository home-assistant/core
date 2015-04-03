"""
homeassistant.components.camera
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Component to interface with various cameras that can be monitored.
"""
import mimetypes
import requests
import logging
from homeassistant.helpers.entity import Entity
import time
from datetime import timedelta
import re
from homeassistant.const import (
    ATTR_ENTITY_PICTURE,
    HTTP_NOT_FOUND)


from homeassistant.helpers.entity_component import EntityComponent


DOMAIN = 'camera'
DEPENDENCIES = ['http']
GROUP_NAME_ALL_CAMERAS = 'all_cameras'
SCAN_INTERVAL = 30
ENTITY_ID_FORMAT = DOMAIN + '.{}'

# Maps discovered services to their platforms
DISCOVERY_PLATFORMS = {}


def setup(hass, config):
    """ Track states and offer events for sensors. """



    component = EntityComponent(
        logging.getLogger(__name__), DOMAIN, hass, SCAN_INTERVAL,
        DISCOVERY_PLATFORMS)

    component.setup(config)


    def _proxy_camera_image(handler, path_match, data):
        """ Proxies the camera image via the HA server. """
        entity_id = path_match.group('entity_id')

        camera = None
        if entity_id in component.entities.keys():
            camera = component.entities[entity_id]

        if camera:
            response = camera.get_camera_image()
            handler.wfile.write(response.content)
        else:
            handler.send_response(HTTP_NOT_FOUND)

    hass.http.register_path('GET', re.compile(r'/api/camera_proxy/(?P<entity_id>[a-zA-Z\._0-9]+)'), _proxy_camera_image, require_auth=True)




    def request_headers():
        return {
            'Cache-Control': 'no-store, no-cache, must-revalidate, pre-check=0, post-check=0, max-age=0',
            'Connection': 'close',
            'Content-Type': 'multipart/x-mixed-replace;boundary=%s' % boundary,
            'Expires': 'Mon, 3 Jan 2000 12:34:56 GMT',
            'Pragma': 'no-cache',
        }

    def image_headers(length):
        return {
            'X-Timestamp': time.time(),
            'Content-Length': length,
            # FIXME: mime-type must be set according file content
            'Content-Type': 'image/jpeg',
        }

    def _proxy_camera_mjpeg_stream(handler, path_match, data):
        """ Proxies the camera image via the HA server. """
        entity_id = path_match.group('entity_id')
        print('test')

        boundary = 'boundarydonotcross'

        image_headers = {
            'X-Timestamp': time.time(),
            'Content-Length': 0,
            # FIXME: mime-type must be set according file content
            'Content-Type': 'image/jpeg',
        }

        request_headers = {
            'Cache-Control': 'no-store, no-cache, must-revalidate, pre-check=0, post-check=0, max-age=0',
            'Connection': 'close',
            'Content-Type': 'multipart/x-mixed-replace; boundary=%s' % boundary,
            'Expires': 'Mon, 3 Jan 2000 12:34:56 GMT',
            'Pragma': 'no-cache',
            #'Content-type': 'image/jpeg'
        }

        camera = None
        if entity_id in component.entities.keys():
            camera = component.entities[entity_id]

        if camera:

            handler.send_response(200)
            # response = camera.get_camera_image()
            # handler.wfile.write(response.content)

            # for k, v in request_headers.items():
            #     #print(k, v)
            #     handler.send_header(k, v)


            handler.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=%s' % boundary)
            handler.end_headers()

            #handler.end_headers()
            #handler.wfile.write(bytes('\n', 'ascii'))

            for idx in range(0,100):
                #print('test')

                # Response headers (multipart)

                # handler.wfile.write(bytes('\r\n', 'ascii'))
                # handler.wfile.write(bytes(boundary, 'ascii'))
                # handler.wfile.write(bytes('\r\n', 'ascii'))

                #handler.end_headers()

                # handler.end_headers()
                # # Part headers
                response = camera.get_camera_image(True)
                #print(response.encoding)
                #image_headers['Content-Length'] = len(response.content)
                image_headers = response.headers
                # for k, v in image_headers.items():
                #     print(k, v)
                #     handler.send_header(k, v)
                #handler.send_header('Content-type', 'image/jpeg')
               #handler.wfile.write(bytes("Content-type: video/x-motion-jpeg", 'ascii'))
                #handler.end_headers()
                #handler.end_headers()
                #handler.end_headers()

                #for chunk in response.iter_content(1024):
                # img_bytes = response.raw.read(20)
                # while len(img_bytes) > 0:
                #     handler.wfile.write(img_bytes)
                #     img_bytes = response.raw.read(20)

                #for chunk in response.iter_content(1024):
                #    handler.wfile.write(chunk)
                #handler.wfile.write(response.content)
                #handler.end_headers()
                handler.wfile.write(response.content)


                #handler.wfile.write(bytes('\r\n', 'ascii'))


                print(str.encode(boundary))

        else:
            handler.send_response(HTTP_NOT_FOUND)

    hass.http.register_path('GET', re.compile(r'/api/camera_proxy_stream/(?P<entity_id>[a-zA-Z\._0-9]+)'), _proxy_camera_mjpeg_stream, require_auth=True)
    return True

    #


class Camera(Entity):
    """ Base class for cameras. """

    def __init__(self, hass, device_info):
        #super().__init__(hass, device_info)
        self.hass = hass
        self.device_info = device_info
        self.BASE_URL = device_info.get('base_url')
        if not self.BASE_URL.endswith('/'):
            self.BASE_URL = self.BASE_URL + '/'
        self.username = device_info.get('username')
        self.password = device_info.get('password')

    def get_camera_image(self, stream=False):
        response = requests.get(self.still_image_url, auth=(self.username, self.password), stream=stream)
        return response

    @property
    def name(self):
        if self.device_info.get('name'):
            return self.device_info.get('name')
        else:
            return super().name


    @property
    def state_attributes(self):
        """ Returns optional state attributes. """
        attr = super().state_attributes
        attr['model_name'] = self.device_info.get('model', 'generic')
        attr['brand'] = self.device_info.get('brand', 'generic')
        attr['still_image_url'] = '/api/camera_proxy/' + self.entity_id
        attr[ATTR_ENTITY_PICTURE] = '/api/camera_proxy/' + self.entity_id + '?api_password=' + self.hass.http.api_password + '&time=' + str(time.time())

        return attr

    @property
    def still_image_url(self):
        """ This should be implemented by different camera models. """
        if self.device_info.get('still_image_url'):
            return self.BASE_URL + self.device_info.get('still_image_url')
        return self.BASE_URL + 'image.jpg'
