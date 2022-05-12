"""Tests for the aws component config and setup."""
from unittest.mock import AsyncMock, MagicMock, patch as async_patch

from homeassistant.setup import async_setup_component


class MockAioSession:
    """Mock AioSession."""

    def __init__(self, *args, **kwargs):
        """Init a mock session."""
        self.get_user = AsyncMock()
        self.invoke = AsyncMock()
        self.publish = AsyncMock()
        self.send_message = AsyncMock()

    def create_client(self, *args, **kwargs):
        """Create a mocked client."""
        return MagicMock(
            __aenter__=AsyncMock(
                return_value=AsyncMock(
                    get_user=self.get_user,  # iam
                    invoke=self.invoke,  # lambda
                    publish=self.publish,  # sns
                    send_message=self.send_message,  # sqs
                )
            ),
            __aexit__=AsyncMock(),
        )

    async def get_available_regions(self, *args, **kwargs):
        """Return list of available regions."""
        return ["us-east-1", "us-east-2", "us-west-1", "us-west-2"]


async def test_empty_config(hass):
    """Test a default config will be create for empty config."""
    mock_session = MockAioSession()
    with async_patch(
        "homeassistant.components.aws.AioSession", return_value=mock_session
    ):
        await async_setup_component(hass, "aws", {"aws": {}})
        await hass.async_block_till_done()

    # we don't validate auto-created default profile
    mock_session.get_user.assert_not_awaited()


async def test_empty_credential(hass):
    """Test a default config will be create for empty credential section."""
    mock_session = MockAioSession()
    with async_patch(
        "homeassistant.components.aws.AioSession", return_value=mock_session
    ):
        await async_setup_component(
            hass,
            "aws",
            {
                "aws": {
                    "notify": [
                        {
                            "service": "lambda",
                            "name": "New Lambda Test",
                            "region_name": "us-east-1",
                        }
                    ]
                }
            },
        )
        await hass.async_block_till_done()

    assert hass.services.has_service("notify", "new_lambda_test") is True
    await hass.services.async_call(
        "notify", "new_lambda_test", {"message": "test", "target": "ARN"}, blocking=True
    )
    mock_session.invoke.assert_awaited_once()


async def test_profile_credential(hass):
    """Test credentials with profile name."""
    mock_session = MockAioSession()
    with async_patch(
        "homeassistant.components.aws.AioSession", return_value=mock_session
    ):

        await async_setup_component(
            hass,
            "aws",
            {
                "aws": {
                    "credentials": {"name": "test", "profile_name": "test-profile"},
                    "notify": [
                        {
                            "service": "sns",
                            "credential_name": "test",
                            "name": "SNS Test",
                            "region_name": "us-east-1",
                        }
                    ],
                }
            },
        )
        await hass.async_block_till_done()

    assert hass.services.has_service("notify", "sns_test") is True
    await hass.services.async_call(
        "notify",
        "sns_test",
        {"title": "test", "message": "test", "target": "ARN"},
        blocking=True,
    )
    mock_session.publish.assert_awaited_once()


async def test_access_key_credential(hass):
    """Test credentials with access key."""
    mock_session = MockAioSession()
    with async_patch(
        "homeassistant.components.aws.AioSession", return_value=mock_session
    ):
        await async_setup_component(
            hass,
            "aws",
            {
                "aws": {
                    "credentials": [
                        {"name": "test", "profile_name": "test-profile"},
                        {
                            "name": "key",
                            "aws_access_key_id": "test-key",
                            "aws_secret_access_key": "test-secret",
                        },
                    ],
                    "notify": [
                        {
                            "service": "sns",
                            "credential_name": "key",
                            "name": "SNS Test",
                            "region_name": "us-east-1",
                        }
                    ],
                }
            },
        )
        await hass.async_block_till_done()

    assert hass.services.has_service("notify", "sns_test") is True
    await hass.services.async_call(
        "notify",
        "sns_test",
        {"title": "test", "message": "test", "target": "ARN"},
        blocking=True,
    )
    mock_session.publish.assert_awaited_once()


async def test_notify_credential(hass):
    """Test notify service can use access key directly."""
    mock_session = MockAioSession()
    with async_patch(
        "homeassistant.components.aws.AioSession", return_value=mock_session
    ), async_patch(
        "homeassistant.components.aws.notify.AioSession", return_value=mock_session
    ):
        await async_setup_component(
            hass,
            "aws",
            {
                "aws": {
                    "notify": [
                        {
                            "service": "sqs",
                            "credential_name": "test",
                            "name": "SQS Test",
                            "region_name": "us-east-1",
                            "aws_access_key_id": "some-key",
                            "aws_secret_access_key": "some-secret",
                        }
                    ]
                }
            },
        )
        await hass.async_block_till_done()

    assert hass.services.has_service("notify", "sqs_test") is True
    await hass.services.async_call(
        "notify", "sqs_test", {"message": "test", "target": "ARN"}, blocking=True
    )


async def test_notify_credential_profile(hass):
    """Test notify service can use profile directly."""
    mock_session = MockAioSession()
    with async_patch(
        "homeassistant.components.aws.AioSession", return_value=mock_session
    ), async_patch(
        "homeassistant.components.aws.notify.AioSession", return_value=mock_session
    ):
        await async_setup_component(
            hass,
            "aws",
            {
                "aws": {
                    "notify": [
                        {
                            "service": "sqs",
                            "name": "SQS Test",
                            "region_name": "us-east-1",
                            "profile_name": "test",
                        }
                    ]
                }
            },
        )
        await hass.async_block_till_done()

    assert hass.services.has_service("notify", "sqs_test") is True
    await hass.services.async_call(
        "notify", "sqs_test", {"message": "test", "target": "ARN"}, blocking=True
    )


async def test_credential_skip_validate(hass):
    """Test credential can skip validate."""
    mock_session = MockAioSession()
    with async_patch(
        "homeassistant.components.aws.AioSession", return_value=mock_session
    ):
        await async_setup_component(
            hass,
            "aws",
            {
                "aws": {
                    "credentials": [
                        {
                            "name": "key",
                            "aws_access_key_id": "not-valid",
                            "aws_secret_access_key": "dont-care",
                            "validate": False,
                        }
                    ]
                }
            },
        )
        await hass.async_block_till_done()

    mock_session.get_user.assert_not_awaited()


async def test_service_call_extra_data(hass):
    """Test service call extra data are parsed properly."""
    mock_session = MockAioSession()
    with async_patch(
        "homeassistant.components.aws.AioSession", return_value=mock_session
    ):
        await async_setup_component(
            hass,
            "aws",
            {
                "aws": {
                    "notify": [
                        {
                            "service": "sns",
                            "name": "SNS Test",
                            "region_name": "us-east-1",
                        }
                    ]
                }
            },
        )
        await hass.async_block_till_done()

    assert hass.services.has_service("notify", "sns_test") is True
    await hass.services.async_call(
        "notify",
        "sns_test",
        {
            "message": "test",
            "target": "ARN",
            "data": {"AWS.SNS.SMS.SenderID": "HA-notify"},
        },
        blocking=True,
    )
    mock_session.publish.assert_called_once_with(
        TargetArn="ARN",
        Message="test",
        Subject="Home Assistant",
        MessageAttributes={
            "AWS.SNS.SMS.SenderID": {"StringValue": "HA-notify", "DataType": "String"}
        },
    )
