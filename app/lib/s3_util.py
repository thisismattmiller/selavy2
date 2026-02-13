import boto3
import os

def get_s3_client():
    """Create an S3 client using environment variables for credentials."""
    return boto3.client(
        's3',
        aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
        region_name='us-east-1'
    )

BUCKET_NAME = 'semlab'
S3_BASE_URL = f'https://{BUCKET_NAME}.s3.amazonaws.com'

def upload_block_text(document_qid, block_id, text, prefix='texts'):
    """Upload block text to S3 and return the public URL.

    Args:
        document_qid: The Wikibase QID of the document (e.g., 'Q12345')
        block_id: The block ID number
        text: The text content to upload
        prefix: The S3 key prefix ('texts' or 'texts_original')

    Returns:
        str: The public S3 URL of the uploaded file
    """
    s3 = get_s3_client()
    key = f'{prefix}/{document_qid}/{block_id}.txt'
    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=key,
        Body=text.encode('utf-8'),
        ContentType='text/plain'
    )
    return f'{S3_BASE_URL}/{key}'
