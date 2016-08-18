"""The tests for the notify smtp platform."""
import unittest

from homeassistant.components.notify import smtp

from tests.common import get_test_home_assistant


class MockSMTP(smtp.MailNotificationService):
    """Test SMTP object that doesn't need a working server."""

    def connection_is_valid(self):
        """Pretend connection is always valid for testing."""
        return True

    def _send_email(self, msg):
        """Just return string for testing."""
        return msg.as_string()


class TestNotifySmtp(unittest.TestCase):
    """Test the smtp notify."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.mailer = MockSMTP('localhost', 25, 'test@test.com', 1, 'testuser',
                               'testpass', 'testrecip@test.com', 0)

    def tearDown(self):  # pylint: disable=invalid-name
        """"Stop down everything that was started."""
        self.hass.stop()

    def test_text_email(self):
        """Test build of default text email behavior."""
        msg = self.mailer.send_message('Test msg')
        expected = ('Content-Type: text/plain; charset="us-ascii"\n'
                    'MIME-Version: 1.0\n'
                    'Content-Transfer-Encoding: 7bit\n'
                    'Subject: \n'
                    'To: testrecip@test.com\n'
                    'From: test@test.com\n'
                    'X-Mailer: HomeAssistant\n'
                    '\n'
                    'Test msg')
        self.assertEqual(msg, expected)

    def test_mixed_email(self):
        """Test build of mixed text email behavior."""
        msg = self.mailer.send_message('Test msg',
                                       data={'images': ['test.jpg']})
        self.assertTrue('Content-Type: multipart/related' in msg)
