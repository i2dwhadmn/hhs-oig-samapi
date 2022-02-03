import json
import os
import re

import boto3


def lambda_handler(event, context):
    print(json.dumps(event, indent=3, default=str))

    file = event["queryStringParameters"]["file"]
    results = get_presigned_url(os.environ["S3_BUCKET"], file)

    return {
        "headers": {"Content-Type": "application/json"},
        "statusCode": 200,
        "body": json.dumps({"url": results}, indent=3, default=str),
        "isBase64Encoded": False,
    }


def get_presigned_url(bucket, key):
    s3 = boto3.client("s3")
    resp = s3.generate_presigned_url(
        "get_object",
        ExpiresIn=60,
        Params={"Bucket": bucket, "Key": key},
    )

    return resp