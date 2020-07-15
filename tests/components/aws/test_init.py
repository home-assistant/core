"""Tests for the aws component config and setup."""
from homeassistant.components import aws
from homeassistant.setup import async_setup_component

from tests.async_mock import AsyncMock, MagicMock, patch as async_patch

MOCK_REKOGNITION_INDEX_FACE_RESPONSE = {
    "FaceRecords": [
        {
            "Face": {
                "FaceId": "12345678-abcd-1234-abcd-12345678abcd",
                "BoundingBox": {
                    "Width": 0.08199405670166016,
                    "Height": 0.22165770828723907,
                    "Left": 0.5035150647163391,
                    "Top": 0.39687681198120117,
                },
                "ImageId": "12345678-abcd-1234-abcd-12345678abcd",
                "ExternalImageId": "camera.demo_camera",
                "Confidence": 99.99530029296875,
            },
            "FaceDetail": {
                "BoundingBox": {
                    "Width": 0.08199405670166016,
                    "Height": 0.22165770828723907,
                    "Left": 0.5035150647163391,
                    "Top": 0.39687681198120117,
                },
                "AgeRange": {"Low": 1, "High": 100},
                "Smile": {"Value": "False", "Confidence": 99.33049011230469},
                "Eyeglasses": {"Value": "False", "Confidence": 99.11644744873047},
                "Sunglasses": {"Value": "False", "Confidence": 99.44528198242188},
                "Gender": {"Value": "Male", "Confidence": 99.54364776611328},
                "Beard": {"Value": "True", "Confidence": 87.48513793945312},
                "Mustache": {"Value": "False", "Confidence": 85.65422821044922},
                "EyesOpen": {"Value": "True", "Confidence": 99.50366973876953},
                "MouthOpen": {"Value": "False", "Confidence": 97.04551696777344},
                "Emotions": [
                    {"Type": "CALM", "Confidence": 77.76014709472656},
                    {"Type": "ANGRY", "Confidence": 16.616424560546875},
                    {"Type": "CONFUSED", "Confidence": 3.2792489528656006},
                ],
                "Landmarks": [],
                "Pose": {
                    "Roll": -5.303612232208252,
                    "Yaw": -9.24954891204834,
                    "Pitch": -0.6200066804885864,
                },
                "Quality": {
                    "Brightness": 89.30477142333984,
                    "Sharpness": 94.08262634277344,
                },
                "Confidence": 99.99530029296875,
            },
        },
    ],
    "FaceModelVersion": "5.0",
    "UnindexedFaces": [],
    "ResponseMetadata": {
        "RequestId": "1bed57e8-0ce3-4c0b-8874-443567ee3354",
        "HTTPStatusCode": 200,
        "HTTPHeaders": {
            "content-type": "application/x-amz-json-1.1",
            "date": "Mon, 04 May 2020 20:11:43 GMT",
            "x-amzn-requestid": "1bed57e8-0ce3-4c0b-8874-443567ee3354",
            "content-length": "3327",
            "connection": "keep-alive",
        },
        "RetryAttempts": 0,
    },
}

MOCK_REKOGNITION_SEARCH_FACE_RESPONSE = {
    "SearchedFaceId": "12345678-abcd-1234-abcd-12345678abcd",
    "FaceMatches": [
        {
            "Similarity": 99.97117614746094,
            "Face": {
                "FaceId": "12345678-abcd-1234-abcd-12345678abcd",
                "BoundingBox": {
                    "Width": 0.25396499037742615,
                    "Height": 0.4246560037136078,
                    "Left": 0.3849340081214905,
                    "Top": 0.27747198939323425,
                },
                "ImageId": "12345678-abcd-1234-abcd-12345678abcd",
                "ExternalImageId": "TestUser",
                "Confidence": 99.99120330810547,
            },
        }
    ],
    "FaceModelVersion": "5.0",
    "ResponseMetadata": {
        "RequestId": "1bed57e8-0ce3-4c0b-8874-443567ee3354",
        "HTTPStatusCode": 200,
        "HTTPHeaders": {
            "content-type": "application/x-amz-json-1.1",
            "date": "Mon, 04 May 2020 20:11:43 GMT",
            "x-amzn-requestid": "1bed57e8-0ce3-4c0b-8874-443567ee3354",
            "content-length": "3327",
            "connection": "keep-alive",
        },
        "RetryAttempts": 0,
    },
}

MOCK_REKOGNITION_OBJECT_RESPONSE = {
    "Labels": [
        {
            "Name": "Human",
            "Confidence": 99.85315704345703,
            "Instances": [],
            "Parents": [],
        },
        {
            "Name": "Person",
            "Confidence": 99.85315704345703,
            "Instances": [
                {
                    "BoundingBox": {
                        "Width": 0.0759148895740509,
                        "Height": 0.5483436584472656,
                        "Left": 0.8748960494995117,
                        "Top": 0.2920868694782257,
                    },
                    "Confidence": 99.85315704345703,
                },
                {
                    "BoundingBox": {
                        "Width": 0.15320314466953278,
                        "Height": 0.515958845615387,
                        "Left": 0.22776539623737335,
                        "Top": 0.2583009898662567,
                    },
                    "Confidence": 89.78672790527344,
                },
            ],
            "Parents": [],
        },
        {
            "Name": "Bike",
            "Confidence": 99.8502426147461,
            "Instances": [],
            "Parents": [{"Name": "Vehicle"}, {"Name": "Transportation"}],
        },
        {
            "Name": "Transportation",
            "Confidence": 99.8502426147461,
            "Instances": [],
            "Parents": [],
        },
        {
            "Name": "Bicycle",
            "Confidence": 99.8502426147461,
            "Instances": [
                {
                    "BoundingBox": {
                        "Width": 0.13132628798484802,
                        "Height": 0.3868344724178314,
                        "Left": 0.22395403683185577,
                        "Top": 0.5006230473518372,
                    },
                    "Confidence": 99.8502426147461,
                }
            ],
            "Parents": [{"Name": "Vehicle"}, {"Name": "Transportation"}],
        },
        {
            "Name": "Vehicle",
            "Confidence": 99.8502426147461,
            "Instances": [],
            "Parents": [{"Name": "Transportation"}],
        },
        {
            "Name": "Automobile",
            "Confidence": 99.36394500732422,
            "Instances": [],
            "Parents": [{"Name": "Vehicle"}, {"Name": "Transportation"}],
        },
        {
            "Name": "Car",
            "Confidence": 99.36394500732422,
            "Instances": [
                {
                    "BoundingBox": {
                        "Width": 0.34410926699638367,
                        "Height": 0.47807249426841736,
                        "Left": 0.2895631790161133,
                        "Top": 0.2647375762462616,
                    },
                    "Confidence": 99.36394500732422,
                }
            ],
            "Parents": [{"Name": "Vehicle"}, {"Name": "Transportation"}],
        },
        {
            "Name": "Shoe",
            "Confidence": 97.61569213867188,
            "Instances": [
                {
                    "BoundingBox": {
                        "Width": 0.0440598800778389,
                        "Height": 0.0466512031853199,
                        "Left": 0.8933280110359192,
                        "Top": 0.7953190207481384,
                    },
                    "Confidence": 97.61569213867188,
                }
            ],
            "Parents": [{"Name": "Clothing"}, {"Name": "Footwear"}],
        },
        {
            "Name": "Cyclist",
            "Confidence": 91.20744323730469,
            "Instances": [],
            "Parents": [
                {"Name": "Bicycle"},
                {"Name": "Sport"},
                {"Name": "Vehicle"},
                {"Name": "Transportation"},
                {"Name": "Person"},
            ],
        },
        {
            "Name": "Sports",
            "Confidence": 91.20744323730469,
            "Instances": [],
            "Parents": [{"Name": "Person"}],
        },
        {
            "Name": "Road",
            "Confidence": 71.86132049560547,
            "Instances": [],
            "Parents": [],
        },
        {
            "Name": "People",
            "Confidence": 58.18419647216797,
            "Instances": [],
            "Parents": [{"Name": "Person"}],
        },
    ],
    "LabelModelVersion": "2.0",
    "ResponseMetadata": {
        "RequestId": "1bed57e8-0ce3-4c0b-8874-443567ee3354",
        "HTTPStatusCode": 200,
        "HTTPHeaders": {
            "content-type": "application/x-amz-json-1.1",
            "date": "Mon, 04 May 2020 20:11:43 GMT",
            "x-amzn-requestid": "1bed57e8-0ce3-4c0b-8874-443567ee3354",
            "content-length": "3327",
            "connection": "keep-alive",
        },
        "RetryAttempts": 0,
    },
}

REKOGNITION_FACE_PARSED_RESPONSE = {
    "name": "TestUser",
    "confidence": 99.99120330810547,
    "bounding_box": {
        "x_min": 0.504,
        "y_min": 0.397,
        "x_max": 0.586,
        "y_max": 0.619,
        "width": 0.082,
        "height": 0.222,
    },
    "entity_id": "image_processing.rekognition_face_demo_camera",
    "centroid": {"x": 0.545, "y": 0.508},
    "gender": "Male",
    "motion": "CALM",
    "glasses": "False",
    "age": 50.5,
}

REKOGNITION_OBJECT_PARSED_RESPONSE = {
    "bounding_box": {
        "height": 0.548,
        "width": 0.076,
        "x_max": 0.951,
        "x_min": 0.875,
        "y_max": 0.84,
        "y_min": 0.292,
    },
    "box_area": 4.163,
    "centroid": {"x": 0.913, "y": 0.566},
    "confidence": 99.853,
    "name": "person",
}


class MockAioSession:
    """Mock AioSession."""

    def __init__(self, *args, **kwargs):
        """Init a mock session."""
        self.get_user = AsyncMock()
        self.invoke = AsyncMock()
        self.publish = AsyncMock()
        self.send_message = AsyncMock()
        self.detect_labels = AsyncMock(return_value=MOCK_REKOGNITION_OBJECT_RESPONSE)
        self.list_collections = AsyncMock()
        self.create_collection = AsyncMock()
        self.index_faces = AsyncMock(return_value=MOCK_REKOGNITION_INDEX_FACE_RESPONSE)
        self.search_faces = AsyncMock(
            return_value=MOCK_REKOGNITION_SEARCH_FACE_RESPONSE
        )

    def create_client(self, *args, **kwargs):  # pylint: disable=no-self-use
        """Create a mocked client."""
        return MagicMock(
            __aenter__=AsyncMock(
                return_value=AsyncMock(
                    get_user=self.get_user,  # iam
                    invoke=self.invoke,  # lambda
                    publish=self.publish,  # sns
                    send_message=self.send_message,  # sqs
                    detect_labels=self.detect_labels,  # rekognition
                    list_collections=self.list_collections,  # rekognition
                    create_collection=self.create_collection,  # rekognition
                    index_faces=self.index_faces,  # rekognition
                    search_faces=self.search_faces,  # rekognition
                )
            ),
            __aexit__=AsyncMock(),
        )

    def set_credentials(self, access_key, secret_key):
        """Mock setting session credentials."""
        return True


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


async def test_image_processing_credential(hass):
    """Test image processing can use access key directly."""
    with async_patch("aiobotocore.AioSession", new=MockAioSession):
        await async_setup_component(
            hass,
            "aws",
            {
                "aws": {
                    "image_processing": [
                        {
                            "service": "rekognition",
                            "platform": "object",
                            "credential_name": "test",
                            "region_name": "us-east-1",
                            "aws_access_key_id": "some-key",
                            "aws_secret_access_key": "some-secret",
                            "source": [{"entity_id": "camera.demo_camera"}],
                        },
                        {
                            "service": "rekognition",
                            "platform": "face",
                            "collection_id": "test-collection",
                            "credential_name": "test",
                            "region_name": "us-east-1",
                            "aws_access_key_id": "some-key",
                            "aws_secret_access_key": "some-secret",
                            "source": [{"entity_id": "camera.demo_camera"}],
                        },
                    ]
                }
            },
        )
        await hass.async_block_till_done()

    sessions = hass.data[aws.DATA_SESSIONS]
    assert sessions is not None
    assert len(sessions) == 1
    assert isinstance(sessions.get("default"), MockAioSession)

    assert hass.states.get("image_processing.rekognition_object_demo_camera")
    assert hass.states.get("image_processing.rekognition_face_demo_camera")


async def test_rekognition_object(hass):
    """Test rekognition object detection functions."""
    with async_patch("aiobotocore.AioSession", new=MockAioSession):
        await async_setup_component(
            hass, "camera", {"camera": {"platform": "demo", "name": "demo camera"}},
        )
        await async_setup_component(
            hass,
            "aws",
            {
                "aws": {
                    "image_processing": [
                        {
                            "service": "rekognition",
                            "platform": "object",
                            "credential_name": "test",
                            "region_name": "us-east-1",
                            "source": [{"entity_id": "camera.demo_camera"}],
                        },
                    ]
                }
            },
        )
        await hass.async_block_till_done()
    await hass.services.async_call(
        "image_processing",
        "scan",
        {"entity_id": "image_processing.rekognition_object_demo_camera"},
        blocking=True,
    )
    state = hass.states.get("image_processing.rekognition_object_demo_camera")
    assert state
    assert len(state.attributes.get("objects")) == 5
    assert len(state.attributes.get("labels")) == 7
    assert state.attributes.get("objects")[0] == REKOGNITION_OBJECT_PARSED_RESPONSE


async def test_rekognition_face(hass):
    """Test rekognition face detection/identification functions."""
    with async_patch("aiobotocore.AioSession", new=MockAioSession):
        await async_setup_component(
            hass, "camera", {"camera": {"platform": "demo", "name": "demo camera"}},
        )
        await async_setup_component(
            hass,
            "aws",
            {
                "aws": {
                    "image_processing": [
                        {
                            "service": "rekognition",
                            "platform": "face",
                            "credential_name": "test",
                            "region_name": "us-east-1",
                            "identify_faces": True,
                            "detection_attributes": "ALL",
                            "collection_id": "testcollection",
                            "source": [{"entity_id": "camera.demo_camera"}],
                        },
                    ]
                }
            },
        )
        await hass.async_block_till_done()
    await hass.services.async_call(
        "image_processing",
        "scan",
        {"entity_id": "image_processing.rekognition_face_demo_camera"},
        blocking=True,
    )
    state = hass.states.get("image_processing.rekognition_face_demo_camera")
    assert state
    assert state.attributes.get("total_faces") == 1
    assert len(state.attributes.get("faces")) == 1
    assert state.attributes.get("faces")[0] == REKOGNITION_FACE_PARSED_RESPONSE


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
