from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from aiobotocore.client import AioBaseClient
from aiobotocore.session import AioSession
import botocore


@asynccontextmanager
async def get_client(data: dict[str, str]) -> AsyncGenerator[AioBaseClient]:
    session = AioSession()
    try:
        async with session.create_client(
            "s3",
            endpoint_url=data.get("endpoint_url"),
            aws_secret_access_key=data["secret_access_key"],
            aws_access_key_id=data["access_key_id"],
        ) as client:
            await client.head_bucket(Bucket=data["bucket"])
            yield client
    except ValueError as err:
        raise InvalidEndpointURLError from err
    except botocore.exceptions.EndpointConnectionError as err:
        raise CannotConnectError from err
    except botocore.exceptions.ClientError as err:
        raise InvalidCredentialsError from err
    except botocore.exceptions.ParamValidationError as err:
        if "Invalid bucket name" in str(err):
            raise InvalidBucketNameError from err


class CannotConnectError(Exception):
    """Error to indicate that the connection to the endpoint failed."""


class InvalidCredentialsError(Exception):
    """Error to indicate that the provided credentials are invalid to reach bucket of given name."""


class InvalidBucketNameError(Exception):
    """Error to indicate that the provided bucket name is invalid."""


class InvalidEndpointURLError(Exception):
    """Error to indicate that the provided endpoint URL is invalid."""
