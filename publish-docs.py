#!/usr/bin/env python3

from argparse import ArgumentParser
import boto3
import hashlib
import logging
import os

logger = logging.getLogger(os.path.basename(__file__))

SRCDIR = os.path.dirname(__file__)
BUILDDIR = os.path.join(SRCDIR, 'build')

ap = ArgumentParser('Publish HTML documentation to S3 bucket')
ap.add_argument('bucket', metavar='BUCKET', help='S3 bucket name')
ap.add_argument('-d', '--builddir', default=BUILDDIR,
                help='path to HTML build directory (default: %(default)s)')
ap.add_argument('--region', help='AWS region of the S3 bucket')
ap.add_argument('-n', '--dry-run', action='store_true',
                help='only show what would be published')
ap.add_argument('--debug', action='store_true',
                help='enable debugging messages')
ap.add_argument('--aws-debug', action='store_true',
                help='enable AWS debugging messages')
args = ap.parse_args()

logging.basicConfig(level=logging.INFO)
if args.debug:
    logger.setLevel(logging.DEBUG)
if args.aws_debug:
    boto3_logger = logging.getLogger('boto3')
    boto3_logger.setLevel(logging.DEBUG)

s3 = boto3.resource('s3', region_name=args.region)
bucket = s3.Bucket(args.bucket)

# Collect all the generated docs into a dictionary.
logger.info('Finding docs files in directory %s', args.builddir)
docs = {}
for root, dirs, files in os.walk(args.builddir):
    for name in files:
        path = os.path.join(root, name)
        key = os.path.relpath(path, args.builddir)
        with open(path, 'rb') as f:
            md5sum = hashlib.md5(f.read()).hexdigest()
        docs[key] = {
            'path': path,
            'size': os.path.getsize(path),
            'e_tag': f'"{md5sum}"',
        }

# Collect all the current objects and their ETags in the bucket into a
# dictionary.
logger.info('Finding current objects in bucket %s', args.bucket)
objects = dict([
    (obj.key, obj) for obj in bucket.objects.all()
])

# Keep a list of changed objects.
changed = []

# Upload all the new objects.
for key, doc in sorted(docs.items()):
    logger.debug(f'Considering {key} for upload')

    # See if there are any changes from an existing object.
    obj = objects.get(key)
    if obj:
        logger.debug(
            f'Comparing {key} to existing S3 object, '
            f'local: size={doc["size"]}, e_tag={doc["e_tag"]}, '
            f's3: size={obj.size}, e_tag={obj.e_tag}'
        )

        # For a non-multipart-upload, S3 will use a quoted md5sum for
        # the ETag and we can compare them directly.
        if len(doc['e_tag']) == len(obj.e_tag):
            if doc['e_tag'] == obj.e_tag:
                logger.debug(f'Skipping {key} upload, matching ETag')
                continue
        else:
            # Otherwise the ETag is generated in S3 and the best we can
            # do is a size comparison since the local timestamps are
            # meaningless.
            if doc['size'] == obj.size:
                logger.debug(f'Skipping {key} upload, matching size')
                continue

    logger.info(f'Uploading {key}')
    changed.append(key)
    if not args.dry_run:
        bucket.upload_file(doc['path'], key)

# Delete any objects that are in S3 but not in the generated docs.
for key in objects.keys() - docs.keys():
    logger.info(f'Deleting {key}')
    obj = objects[key]
    changed.append(key)
    if not args.dry_run:
        obj.delete()

if len(changed) == 0:
    logger.info('All objects up to date')
