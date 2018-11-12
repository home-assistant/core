"""The tests for the notify smtp platform."""
import unittest
from unittest.mock import patch

from homeassistant.components.notify import smtp

from tests.common import get_test_home_assistant
import re


class MockSMTP(smtp.MailNotificationService):
    """Test SMTP object that doesn't need a working server."""

    def _send_email(self, msg):
        """Just return string for testing."""
        return msg.as_string()


class TestNotifySmtp(unittest.TestCase):
    """Test the smtp notify."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.mailer = MockSMTP('localhost', 25, 5, 'test@test.com', 1,
                               'testuser', 'testpass',
                               ['recip1@example.com', 'testrecip@test.com'],
                               'HomeAssistant', 0)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    @patch('email.utils.make_msgid', return_value='<mock@mock>')
    def test_text_email(self, mock_make_msgid):
        """Test build of default text email behavior."""
        msg = self.mailer.send_message('Test msg')
        expected = ('^Content-Type: text/plain; charset="us-ascii"\n'
                    'MIME-Version: 1.0\n'
                    'Content-Transfer-Encoding: 7bit\n'
                    'Subject: Home Assistant\n'
                    'To: recip1@example.com,testrecip@test.com\n'
                    'From: HomeAssistant <test@test.com>\n'
                    'X-Mailer: HomeAssistant\n'
                    'Date: [^\n]+\n'
                    'Message-Id: <[^@]+@[^>]+>\n'
                    '\n'
                    'Test msg$')
        assert re.search(expected, msg)

    @patch('email.utils.make_msgid', return_value='<mock@mock>')
    def test_mixed_email(self, mock_make_msgid):
        """Test build of mixed text email behavior."""
        msg = self.mailer.send_message('Test msg',
                                       data={'images': ['test.jpg']})
        assert 'Content-Type: multipart/related' in msg

    @patch('email.utils.make_msgid', return_value='<mock@mock>')
    def test_html_email(self, mock_make_msgid):
        """Test build of html email behavior."""
        html = '''
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
        </html>'''
        msg = self.mailer.send_message('Test msg',
                                       data={'html': html,
                                             'images': ['test.jpg']})
        assert 'Content-Type: multipart/related' in msg
