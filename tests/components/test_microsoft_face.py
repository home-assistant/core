"""The tests for the microsoft face platform."""
import asyncio
from unittest.mock import patch

import homeassistant.components.microsoft_face as mf
from homeassistant.setup import setup_component

from tests.common import (
    get_test_home_assistant, assert_setup_component, mock_coro, load_fixture)


class TestMicrosoftFaceSetup(object):
    """Test the microsoft face component."""

    def setup_method(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

        self.config = {
            mf.DOMAIN: {
                'api_key': '12345678abcdef',
            }
        }

        self.endpoint_url = "https://westus.{0}".format(mf.FACE_API_URL)

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    @patch('homeassistant.components.microsoft_face.'
           'MicrosoftFace.update_store', return_value=mock_coro())
    def test_setup_component(self, mock_update):
        """Setup component."""
        with assert_setup_component(3, mf.DOMAIN):
            setup_component(self.hass, mf.DOMAIN, self.config)

    @patch('homeassistant.components.microsoft_face.'
           'MicrosoftFace.update_store', return_value=mock_coro())
    def test_setup_component_wrong_api_key(self, mock_update):
        """Setup component without api key."""
        with assert_setup_component(0, mf.DOMAIN):
            setup_component(self.hass, mf.DOMAIN, {mf.DOMAIN: {}})

    @patch('homeassistant.components.microsoft_face.'
           'MicrosoftFace.update_store', return_value=mock_coro())
    def test_setup_component_test_service(self, mock_update):
        """Setup component."""
        with assert_setup_component(3, mf.DOMAIN):
            setup_component(self.hass, mf.DOMAIN, self.config)

        assert self.hass.services.has_service(mf.DOMAIN, 'create_group')
        assert self.hass.services.has_service(mf.DOMAIN, 'delete_group')
        assert self.hass.services.has_service(mf.DOMAIN, 'train_group')
        assert self.hass.services.has_service(mf.DOMAIN, 'create_person')
        assert self.hass.services.has_service(mf.DOMAIN, 'delete_person')
        assert self.hass.services.has_service(mf.DOMAIN, 'face_person')

    def test_setup_component_test_entities(self, aioclient_mock):
        """Setup component."""
        aioclient_mock.get(
            self.endpoint_url.format("persongroups"),
            text=load_fixture('microsoft_face_persongroups.json')
        )
        aioclient_mock.get(
            self.endpoint_url.format("persongroups/test_group1/persons"),
            text=load_fixture('microsoft_face_persons.json')
        )
        aioclient_mock.get(
            self.endpoint_url.format("persongroups/test_group2/persons"),
            text=load_fixture('microsoft_face_persons.json')
        )

        with assert_setup_component(3, mf.DOMAIN):
            setup_component(self.hass, mf.DOMAIN, self.config)

        assert len(aioclient_mock.mock_calls) == 3

        entity_group1 = self.hass.states.get('microsoft_face.test_group1')
        entity_group2 = self.hass.states.get('microsoft_face.test_group2')

        assert entity_group1 is not None
        assert entity_group2 is not None

        assert entity_group1.attributes['Ryan'] == \
            '25985303-c537-4467-b41d-bdb45cd95ca1'
        assert entity_group1.attributes['David'] == \
            '2ae4935b-9659-44c3-977f-61fac20d0538'

        assert entity_group2.attributes['Ryan'] == \
            '25985303-c537-4467-b41d-bdb45cd95ca1'
        assert entity_group2.attributes['David'] == \
            '2ae4935b-9659-44c3-977f-61fac20d0538'

    @patch('homeassistant.components.microsoft_face.'
           'MicrosoftFace.update_store', return_value=mock_coro())
    def test_service_groups(self, mock_update, aioclient_mock):
        """Setup component, test groups services."""
        aioclient_mock.put(
            self.endpoint_url.format("persongroups/service_group"),
            status=200, text="{}"
        )
        aioclient_mock.delete(
            self.endpoint_url.format("persongroups/service_group"),
            status=200, text="{}"
        )

        with assert_setup_component(3, mf.DOMAIN):
            setup_component(self.hass, mf.DOMAIN, self.config)

        mf.create_group(self.hass, 'Service Group')
        self.hass.block_till_done()

        entity = self.hass.states.get('microsoft_face.service_group')
        assert entity is not None
        assert len(aioclient_mock.mock_calls) == 1

        mf.delete_group(self.hass, 'Service Group')
        self.hass.block_till_done()

        entity = self.hass.states.get('microsoft_face.service_group')
        assert entity is None
        assert len(aioclient_mock.mock_calls) == 2

    def test_service_person(self, aioclient_mock):
        """Setup component, test person services."""
        aioclient_mock.get(
            self.endpoint_url.format("persongroups"),
            text=load_fixture('microsoft_face_persongroups.json')
        )
        aioclient_mock.get(
            self.endpoint_url.format("persongroups/test_group1/persons"),
            text=load_fixture('microsoft_face_persons.json')
        )
        aioclient_mock.get(
            self.endpoint_url.format("persongroups/test_group2/persons"),
            text=load_fixture('microsoft_face_persons.json')
        )

        with assert_setup_component(3, mf.DOMAIN):
            setup_component(self.hass, mf.DOMAIN, self.config)

        assert len(aioclient_mock.mock_calls) == 3

        aioclient_mock.post(
            self.endpoint_url.format("persongroups/test_group1/persons"),
            text=load_fixture('microsoft_face_create_person.json')
        )
        aioclient_mock.delete(
            self.endpoint_url.format(
                "persongroups/test_group1/persons/"
                "25985303-c537-4467-b41d-bdb45cd95ca1"),
            status=200, text="{}"
        )

        mf.create_person(self.hass, 'test group1', 'Hans')
        self.hass.block_till_done()

        entity_group1 = self.hass.states.get('microsoft_face.test_group1')

        assert len(aioclient_mock.mock_calls) == 4
        assert entity_group1 is not None
        assert entity_group1.attributes['Hans'] == \
            '25985303-c537-4467-b41d-bdb45cd95ca1'

        mf.delete_person(self.hass, 'test group1', 'Hans')
        self.hass.block_till_done()

        entity_group1 = self.hass.states.get('microsoft_face.test_group1')

        assert len(aioclient_mock.mock_calls) == 5
        assert entity_group1 is not None
        assert 'Hans' not in entity_group1.attributes

    @patch('homeassistant.components.microsoft_face.'
           'MicrosoftFace.update_store', return_value=mock_coro())
    def test_service_train(self, mock_update, aioclient_mock):
        """Setup component, test train groups services."""
        with assert_setup_component(3, mf.DOMAIN):
            setup_component(self.hass, mf.DOMAIN, self.config)

        aioclient_mock.post(
            self.endpoint_url.format("persongroups/service_group/train"),
            status=200, text="{}"
        )

        mf.train_group(self.hass, 'Service Group')
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 1

    @patch('homeassistant.components.camera.async_get_image',
           return_value=mock_coro(b'Test'))
    def test_service_face(self, camera_mock, aioclient_mock):
        """Setup component, test person face services."""
        aioclient_mock.get(
            self.endpoint_url.format("persongroups"),
            text=load_fixture('microsoft_face_persongroups.json')
        )
        aioclient_mock.get(
            self.endpoint_url.format("persongroups/test_group1/persons"),
            text=load_fixture('microsoft_face_persons.json')
        )
        aioclient_mock.get(
            self.endpoint_url.format("persongroups/test_group2/persons"),
            text=load_fixture('microsoft_face_persons.json')
        )

        self.config['camera'] = {'platform': 'demo'}
        with assert_setup_component(3, mf.DOMAIN):
            setup_component(self.hass, mf.DOMAIN, self.config)

        assert len(aioclient_mock.mock_calls) == 3

        aioclient_mock.post(
            self.endpoint_url.format(
                "persongroups/test_group2/persons/"
                "2ae4935b-9659-44c3-977f-61fac20d0538/persistedFaces"),
            status=200, text="{}"
        )

        mf.face_person(
            self.hass, 'test_group2', 'David', 'camera.demo_camera')
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 4
        assert aioclient_mock.mock_calls[3][2] == b'Test'

    @patch('homeassistant.components.microsoft_face.'
           'MicrosoftFace.update_store', return_value=mock_coro())
    def test_service_status_400(self, mock_update, aioclient_mock):
        """Setup component, test groups services with error."""
        aioclient_mock.put(
            self.endpoint_url.format("persongroups/service_group"),
            status=400, text="{'error': {'message': 'Error'}}"
        )

        with assert_setup_component(3, mf.DOMAIN):
            setup_component(self.hass, mf.DOMAIN, self.config)

        mf.create_group(self.hass, 'Service Group')
        self.hass.block_till_done()

        entity = self.hass.states.get('microsoft_face.service_group')
        assert entity is None
        assert len(aioclient_mock.mock_calls) == 1

    @patch('homeassistant.components.microsoft_face.'
           'MicrosoftFace.update_store', return_value=mock_coro())
    def test_service_status_timeout(self, mock_update, aioclient_mock):
        """Setup component, test groups services with timeout."""
        aioclient_mock.put(
            self.endpoint_url.format("persongroups/service_group"),
            status=400, exc=asyncio.TimeoutError()
        )

        with assert_setup_component(3, mf.DOMAIN):
            setup_component(self.hass, mf.DOMAIN, self.config)

        mf.create_group(self.hass, 'Service Group')
        self.hass.block_till_done()

        entity = self.hass.states.get('microsoft_face.service_group')
        assert entity is None
        assert len(aioclient_mock.mock_calls) == 1
