#!/usr/bin/env python3

# publish-docs.py - Publish changed files to AWS S3
#
# Copyright © 2021 Endless OS Foundation LLC
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

from argparse import ArgumentParser
import boto3
import hashlib
import logging
import magic
import os
import time

logger = logging.getLogger(os.path.basename(__file__))

SRCDIR = os.path.dirname(__file__)
BUILDDIR = os.path.join(SRCDIR, 'build')
EXT_MIME_TYPES = {
    '.css': 'text/css',
    '.html': 'text/html',
    '.js': 'text/javascript',
}

ap = ArgumentParser('Publish HTML documentation to S3 bucket')
ap.add_argument('bucket', metavar='BUCKET', help='S3 bucket name')
ap.add_argument('-c', '--cloudfront',
                help='CloudFront distribution ID for invalidation')
ap.add_argument('-d', '--builddir', default=BUILDDIR,
                help='path to HTML build directory (default: %(default)s)')
ap.add_argument('-b', '--branch', help='publish only BRANCH subdirectory')
ap.add_argument('--region', help='AWS region of the S3 bucket')
ap.add_argument('-f', '--force', action='store_true',
                help='force publishing of all objects')
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
if args.branch:
    walkdir = os.path.join(args.builddir, args.branch)
else:
    walkdir = args.builddir
logger.info('Finding docs files in directory %s', walkdir)
docs = {}
for root, dirs, files in os.walk(walkdir):
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
if args.branch:
    logger.info(
        'Finding current objects in bucket %s directory %s',
        args.bucket,
        args.branch,
    )
    objects_iter = bucket.objects.filter(Prefix=f'{args.branch}/')
else:
    logger.info('Finding current objects in bucket %s', args.bucket)
    objects_iter = bucket.objects.all()

objects = dict([(obj.key, obj) for obj in objects_iter])

# Keep a list of changed objects.
changed = []

# Upload all the new objects.
for key, doc in sorted(docs.items()):
    logger.debug(f'Considering {key} for upload')

    # See if there are any changes from an existing object.
    obj = objects.get(key)
    if obj and not args.force:
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

    # Figure out the content type. libmagic sets many files to
    # text/plain, so first we do some simple file extension matching.
    file_ext = os.path.splitext(doc['path'])[1]
    content_type = EXT_MIME_TYPES.get(file_ext)
    if not content_type:
        # Use libmagic to get the type.
        content_type = magic.from_file(doc['path'], mime=True)
    logger.debug(f'Using ContentType {content_type} for {key}')

    logger.info(f'Uploading {key}')
    changed.append(key)
    if not args.dry_run:
        bucket.upload_file(doc['path'], key,
                           ExtraArgs={'ContentType': content_type})

# Delete any objects that are in S3 but not in the generated docs.
for key in objects.keys() - docs.keys():
    logger.info(f'Deleting {key}')
    obj = objects[key]
    changed.append(key)
    if not args.dry_run:
        obj.delete()

if len(changed) == 0:
    logger.info('All objects up to date')
elif args.cloudfront:
    # CloudFront is regionless, so don't specify a region.
    cloudfront = boto3.client('cloudfront')

    # Build the paths to invalidate. If --force was specified, then just
    # invalidate the entire distribution.
    if args.force:
        logger.info('Adding invalidation path /*')
        paths = ['/*']
    else:
        paths = []
        for key in changed:
            path = f'/{key}'
            logger.info(f'Adding invalidation path {path}')
            paths.append(path)

            # The S3 bucket is setup for static website hosting with any
            # URLs ending in / being treated as /index.html. Invalidate
            # the nameless path, too.
            if os.path.basename(path) == 'index.html':
                keydir = os.path.dirname(path)
                if keydir != '/':
                    keydir += '/'
                logger.info(f'Adding invalidation path {keydir}')
                paths.append(keydir)

    # CloudFront allows up to 3000 maximum concurrent invalidation
    # files. Since we might have a couple concurrent builds going,
    # switch to the full distribution invalidation at 1000 paths. The
    # only time we even approach this is when switching branches and in
    # that case we might as well invalidate everything.
    #
    # https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/Invalidation.html#InvalidationLimits
    if len(paths) >= 1000:
        logger.warning(
            f'{len(paths)} invalidation paths may exceed CloudFront limit. '
            'Using full /* invalidation path instead.'
        )
        paths = ['/*']

    # Make a unique CallerReference value from the current time.
    caller_ref = str(time.time_ns())

    # Create the CloudFront invalidation.
    logger.info(f'Invalidating CloudFront distribution {args.cloudfront}')
    if not args.dry_run:
        resp = cloudfront.create_invalidation(
            DistributionId=args.cloudfront,
            InvalidationBatch={
                'Paths': {
                    'Quantity': len(paths),
                    'Items': paths,
                },
                'CallerReference': caller_ref,
            }
        )
        logger.debug(
            f'Created invalidation {resp["Invalidation"]["Id"]} '
            f'({resp["Location"]})'
        )
