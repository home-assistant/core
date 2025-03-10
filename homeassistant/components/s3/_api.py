from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from aiobotocore.client import AioBaseClient
from aiobotocore.session import AioSession
from botocore.exceptions import (
    ClientError,
    EndpointConnectionError,
    ParamValidationError,
)


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
    except EndpointConnectionError as err:
        raise CannotConnectError from err
    except ClientError as err:
        raise InvalidCredentialsError from err
    except ParamValidationError as err:
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
