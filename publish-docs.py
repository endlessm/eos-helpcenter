#!/usr/bin/env python3

from argparse import ArgumentParser
import os
import subprocess

SRCDIR = os.path.dirname(__file__)
BUILDDIR = os.path.join(SRCDIR, 'build')

ap = ArgumentParser('Publish HTML documentation to S3 bucket')
ap.add_argument('bucket', metavar='BUCKET', help='S3 bucket name')
ap.add_argument('-d', '--builddir', default=BUILDDIR,
                help='path to HTML build directory (default: %(default)s)')
ap.add_argument('--region', help='AWS region of the S3 bucket')
ap.add_argument('-n', '--dry-run', action='store_true',
                help='only show what would be published')
args = ap.parse_args()

cmd = ['aws', 's3', 'sync']
if args.dry_run:
    cmd.append('--dryrun')
if args.region:
    cmd += ['--region', args.region]
cmd += [
    '--delete',
    # Build timestamps are always updated during the build, so ignore them
    '--size-only',
    args.builddir,
    's3:///{}'.format(args.bucket)
]

print('Syncing', args.builddir, 'to', args.bucket)
subprocess.check_call(cmd)
