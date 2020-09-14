"""The tests for the notify smtp platform."""
from os import path
import re
import unittest

from homeassistant import config as hass_config
import homeassistant.components.notify as notify
from homeassistant.components.smtp import DOMAIN
from homeassistant.components.smtp.notify import MailNotificationService
from homeassistant.const import SERVICE_RELOAD
from homeassistant.setup import async_setup_component

from tests.async_mock import patch
from tests.common import get_test_home_assistant


class MockSMTP(MailNotificationService):
    """Test SMTP object that doesn't need a working server."""

    def _send_email(self, msg):
        """Just return string for testing."""
        return msg.as_string()


class TestNotifySmtp(unittest.TestCase):
    """Test the smtp notify."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.mailer = MockSMTP(
            "localhost",
            25,
            5,
            "test@test.com",
            1,
            "testuser",
            "testpass",
            ["recip1@example.com", "testrecip@test.com"],
            "Home Assistant",
            0,
        )
        self.addCleanup(self.tear_down_cleanup)

    def tear_down_cleanup(self):
        """Stop down everything that was started."""
        self.hass.stop()

    @patch("email.utils.make_msgid", return_value="<mock@mock>")
    def test_text_email(self, mock_make_msgid):
        """Test build of default text email behavior."""
        msg = self.mailer.send_message("Test msg")
        expected = (
            '^Content-Type: text/plain; charset="us-ascii"\n'
            "MIME-Version: 1.0\n"
            "Content-Transfer-Encoding: 7bit\n"
            "Subject: Home Assistant\n"
            "To: recip1@example.com,testrecip@test.com\n"
            "From: Home Assistant <test@test.com>\n"
            "X-Mailer: Home Assistant\n"
            "Date: [^\n]+\n"
            "Message-Id: <[^@]+@[^>]+>\n"
            "\n"
            "Test msg$"
        )
        assert re.search(expected, msg)

    @patch("email.utils.make_msgid", return_value="<mock@mock>")
    def test_mixed_email(self, mock_make_msgid):
        """Test build of mixed text email behavior."""
        msg = self.mailer.send_message("Test msg", data={"images": ["test.jpg"]})
        assert "Content-Type: multipart/related" in msg

    @patch("email.utils.make_msgid", return_value="<mock@mock>")
    def test_html_email(self, mock_make_msgid):
        """Test build of html email behavior."""
        html = """
        <!DOCTYPE html>
        <html lang="en" xmlns="http://www.w3.org/1999/xhtml">
            <head><meta charset="UTF-8"></head>
            <body>
              <div>
                <h1>Intruder alert at apartment!!</h1>
              </div>
              <div>
                <img alt="test.jpg" src="cid:test.jpg"/>
              </div>
            </body>
        </html>"""
        msg = self.mailer.send_message(
            "Test msg", data={"html": html, "images": ["test.jpg"]}
        )
        assert "Content-Type: multipart/related" in msg


async def test_reload_notify(hass):
    """Verify we can reload the notify service."""

    with patch(
        "homeassistant.components.smtp.notify.MailNotificationService.connection_is_valid"
    ):
        assert await async_setup_component(
            hass,
            notify.DOMAIN,
            {
                notify.DOMAIN: [
                    {
                        "name": DOMAIN,
                        "platform": DOMAIN,
                        "recipient": "test@example.com",
                        "sender": "test@example.com",
                    },
                ]
            },
        )
        await hass.async_block_till_done()

    assert hass.services.has_service(notify.DOMAIN, DOMAIN)

    yaml_path = path.join(
        _get_fixtures_base_path(),
        "fixtures",
        "smtp/configuration.yaml",
    )
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path), patch(
        "homeassistant.components.smtp.notify.MailNotificationService.connection_is_valid"
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert not hass.services.has_service(notify.DOMAIN, DOMAIN)
    assert hass.services.has_service(notify.DOMAIN, "smtp_reloaded")


def _get_fixtures_base_path():
    return path.dirname(path.dirname(path.dirname(__file__)))
