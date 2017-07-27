"""The tests for the mailbox component."""
import json
import requests
from hashlib import sha1

from homeassistant.setup import setup_component
import homeassistant.components.mailbox as mailbox
import homeassistant.components.http as http

from tests.common import (
    get_test_home_assistant, get_test_instance_port, assert_setup_component)


class TestSetupMailbox(object):
    """Verify mailbox creation."""

    def setup_method(self):
        """Initialize mailbox platform."""
        self.hass = get_test_home_assistant()

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_component(self):
        """Initialize demo platform on mailbox component."""
        config = {
            mailbox.DOMAIN: {
                'platform': 'demo'
            }
        }

        with assert_setup_component(1, mailbox.DOMAIN):
            setup_component(self.hass, mailbox.DOMAIN, config)


class TestMailbox(object):
    """Test class for mailbox."""

    def setup_method(self):
        """Initialize platform."""
        self.hass = get_test_home_assistant()

        setup_component(
            self.hass, http.DOMAIN,
            {http.DOMAIN: {http.CONF_SERVER_PORT: get_test_instance_port()}})

        config = {
            mailbox.DOMAIN: {
                'platform': 'demo'
            }
        }

        setup_component(self.hass, mailbox.DOMAIN, config)

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_get_messages_from_mailbox(self):
        """Get messages from mailbox entity."""
        self.hass.start()

        url = ("{}/api/mailbox/messages/mailbox.demo_mailbox"
               ).format(self.hass.config.api.base_url)

        req = requests.get(url)
        assert req.status_code == 200
        result = json.loads(req.content.decode("utf-8"))
        assert len(result) == 10

    def test_get_media_from_mailbox(self):
        """Get audio from mailbox entity."""
        self.hass.start()

        mp3sha = "fd638337fa269e41fd5ce932aa24f8341bd40589"
        msgtxt = "This is recorded message # 1"
        msgsha = sha1(msgtxt.encode('utf-8')).hexdigest()

        url = ("{}/api/mailbox/media/mailbox.demo_mailbox/%s"
               % (msgsha)).format(self.hass.config.api.base_url)
        req = requests.get(url)
        assert req.status_code == 200
        assert sha1(req.content).hexdigest() == mp3sha

    def test_delete_from_mailbox(self):
        """Get audio from mailbox entity."""
        self.hass.start()

        msgtxt1 = "This is recorded message # 1"
        msgtxt2 = "This is recorded message # 2"
        msgsha1 = sha1(msgtxt1.encode('utf-8')).hexdigest()
        msgsha2 = sha1(msgtxt2.encode('utf-8')).hexdigest()

        url = ("{}/api/mailbox/delete/mailbox.demo_mailbox"
               ).format(self.hass.config.api.base_url)
        req = requests.post(url, data=json.dumps([msgsha1, msgsha2]))
        assert req.status_code == 200

        url = ("{}/api/mailbox/messages/mailbox.demo_mailbox"
               ).format(self.hass.config.api.base_url)

        req = requests.get(url)
        assert req.status_code == 200
        result = json.loads(req.content.decode("utf-8"))
        assert len(result) == 8

    def test_get_messages_from_invalid_mailbox(self):
        """Get messages from mailbox entity."""
        self.hass.start()

        url = ("{}/api/mailbox/messages/mailbox.invalid_mailbox"
               ).format(self.hass.config.api.base_url)

        req = requests.get(url)
        assert req.status_code == 401

    def test_get_media_from_invalid_mailbox(self):
        """Get messages from mailbox entity."""
        self.hass.start()

        msgsha = "0000000000000000000000000000000000000000"
        url = ("{}/api/mailbox/media/mailbox.invalid_mailbox/%s"
               % (msgsha)).format(self.hass.config.api.base_url)

        req = requests.get(url)
        assert req.status_code == 401

    def test_get_media_from_invalid_msgid(self):
        """Get messages from mailbox entity."""
        self.hass.start()

        msgsha = "0000000000000000000000000000000000000000"
        url = ("{}/api/mailbox/media/mailbox.demo_mailbox/%s"
               % (msgsha)).format(self.hass.config.api.base_url)

        req = requests.get(url)
        assert req.status_code == 500

    def test_delete_from_invalid_mailbox(self):
        """Get audio from mailbox entity."""
        self.hass.start()

        msgsha = "0000000000000000000000000000000000000000"
        url = ("{}/api/mailbox/delete/mailbox.invalid_mailbox"
               ).format(self.hass.config.api.base_url)
        req = requests.post(url, data=msgsha)
        assert req.status_code == 401

    def test_delete_from_malformed_post(self):
        """Get audio from mailbox entity."""
        self.hass.start()

        badjson = '["0000000000000000000000000000000000000000"'
        url = ("{}/api/mailbox/delete/mailbox.demo_mailbox"
               ).format(self.hass.config.api.base_url)
        req = requests.post(url, data=badjson)
        assert req.status_code == 400
