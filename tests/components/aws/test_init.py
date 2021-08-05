"""Tests for the aws component config and setup."""
from unittest.mock import AsyncMock, MagicMock, patch as async_patch

from homeassistant.components import aws
from homeassistant.setup import async_setup_component


class MockAioSession:
    """Mock AioSession."""

    def __init__(self, *args, **kwargs):
        """Init a mock session."""
        self.get_user = AsyncMock()
        self.invoke = AsyncMock()
        self.publish = AsyncMock()
        self.send_message = AsyncMock()

    def create_client(self, *args, **kwargs):  # pylint: disable=no-self-use
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


async def test_empty_config(hass):
    """Test a default config will be create for empty config."""
    with async_patch("aiobotocore.AioSession", new=MockAioSession):
        await async_setup_component(hass, "aws", {"aws": {}})
        await hass.async_block_till_done()

    sessions = hass.data[aws.DATA_SESSIONS]
    assert sessions is not None
    assert len(sessions) == 1
    session = sessions.get("default")
    assert isinstance(session, MockAioSession)
    # we don't validate auto-created default profile
    session.get_user.assert_not_awaited()


async def test_empty_credential(hass):
    """Test a default config will be create for empty credential section."""
    with async_patch("aiobotocore.AioSession", new=MockAioSession):
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

    sessions = hass.data[aws.DATA_SESSIONS]
    assert sessions is not None
    assert len(sessions) == 1
    session = sessions.get("default")
    assert isinstance(session, MockAioSession)

    assert hass.services.has_service("notify", "new_lambda_test") is True
    await hass.services.async_call(
        "notify", "new_lambda_test", {"message": "test", "target": "ARN"}, blocking=True
    )
    session.invoke.assert_awaited_once()


async def test_profile_credential(hass):
    """Test credentials with profile name."""
    with async_patch("aiobotocore.AioSession", new=MockAioSession):
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

    sessions = hass.data[aws.DATA_SESSIONS]
    assert sessions is not None
    assert len(sessions) == 1
    session = sessions.get("test")
    assert isinstance(session, MockAioSession)

    assert hass.services.has_service("notify", "sns_test") is True
    await hass.services.async_call(
        "notify",
        "sns_test",
        {"title": "test", "message": "test", "target": "ARN"},
        blocking=True,
    )
    session.publish.assert_awaited_once()


async def test_access_key_credential(hass):
    """Test credentials with access key."""
    with async_patch("aiobotocore.AioSession", new=MockAioSession):
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

    sessions = hass.data[aws.DATA_SESSIONS]
    assert sessions is not None
    assert len(sessions) == 2
    session = sessions.get("key")
    assert isinstance(session, MockAioSession)

    assert hass.services.has_service("notify", "sns_test") is True
    await hass.services.async_call(
        "notify",
        "sns_test",
        {"title": "test", "message": "test", "target": "ARN"},
        blocking=True,
    )
    session.publish.assert_awaited_once()


async def test_notify_credential(hass):
    """Test notify service can use access key directly."""
    with async_patch("aiobotocore.AioSession", new=MockAioSession):
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

    sessions = hass.data[aws.DATA_SESSIONS]
    assert sessions is not None
    assert len(sessions) == 1
    assert isinstance(sessions.get("default"), MockAioSession)

    assert hass.services.has_service("notify", "sqs_test") is True
    await hass.services.async_call(
        "notify", "sqs_test", {"message": "test", "target": "ARN"}, blocking=True
    )


async def test_notify_credential_profile(hass):
    """Test notify service can use profile directly."""
    with async_patch("aiobotocore.AioSession", new=MockAioSession):
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

    sessions = hass.data[aws.DATA_SESSIONS]
    assert sessions is not None
    assert len(sessions) == 1
    assert isinstance(sessions.get("default"), MockAioSession)

    assert hass.services.has_service("notify", "sqs_test") is True
    await hass.services.async_call(
        "notify", "sqs_test", {"message": "test", "target": "ARN"}, blocking=True
    )


async def test_credential_skip_validate(hass):
    """Test credential can skip validate."""
    with async_patch("aiobotocore.AioSession", new=MockAioSession):
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

    sessions = hass.data[aws.DATA_SESSIONS]
    assert sessions is not None
    assert len(sessions) == 1
    session = sessions.get("key")
    assert isinstance(session, MockAioSession)
    session.get_user.assert_not_awaited()
