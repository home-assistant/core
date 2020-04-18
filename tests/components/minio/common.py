"""Minio Test event."""
TEST_EVENT = {
    "Records": [
        {
            "eventVersion": "2.0",
            "eventSource": "minio:s3",
            "awsRegion": "",
            "eventTime": "2019-05-02T11:05:07Z",
            "eventName": "s3:ObjectCreated:Put",
            "userIdentity": {"principalId": "SO9KNO6YT9OGE39PQCZW"},
            "requestParameters": {
                "accessKey": "SO9KNO6YT9OGE39PQCZW",
                "region": "",
                "sourceIPAddress": "172.27.0.1",
            },
            "responseElements": {
                "x-amz-request-id": "159AD8E6F6805783",
                "x-minio-deployment-id": "90b265b8-bac5-413a-b12a-8915469fd769",
                "x-minio-origin-endpoint": "http://172.27.0.2:9000",
            },
            "s3": {
                "s3SchemaVersion": "1.0",
                "configurationId": "Config",
                "bucket": {
                    "name": "test",
                    "ownerIdentity": {"principalId": "SO9KNO6YT9OGE39PQCZW"},
                    "arn": "arn:aws:s3:::test",
                },
                "object": {
                    "key": "5jJkTAo.jpg",
                    "size": 108368,
                    "eTag": "1af324731637228cbbb0b2e8c07d4e50",
                    "contentType": "image/jpeg",
                    "userMetadata": {"content-type": "image/jpeg"},
                    "versionId": "1",
                    "sequencer": "159AD8E6F76DD9C4",
                },
            },
            "source": {
                "host": "",
                "port": "",
                "userAgent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_3) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/12.0.3 Safari/605.1.15",
            },
        }
    ]
}
