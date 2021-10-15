import pytest
from pysignalclirestapi import SignalCliRestApi

from homeassistant.components.signal_messenger.notify import SignalNotificationService


@pytest.fixture
def signal_notification_service():
    """Setting up signal notification service"""
    recipients = ["+435565656565"]
    number = "+43443434343"
    client = SignalCliRestApi("http://127.0.0.1:8080", number)
    return SignalNotificationService(recipients, client)
