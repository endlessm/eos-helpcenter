#!/bin/bash

set -e

SRCDIR=$(dirname "$0")
BUILDDIR="$SRCDIR/build"
REGION=
DRY_RUN=false

ARGS=$(getopt -n "$0" -o d:nh -l builddir:,region:,dry-run,help -- "$@")
eval set -- "$ARGS"

usage() {
    cat <<EOF
Usage: $0 [OPTION...] BUCKET

Publish HTML to documentation to S3 bucket

  -d, --builddir	path to HTML build directory (default: $BUILDDIR)
  --region		AWS region of the S3 bucket
  -n, --dry-run		only show what would be published
  -h, --help		show this help message an exit
EOF
}

while true; do
    case "$1" in
	-d|--builddir)
	    BUILDDIR=$2
	    shift 2
	    ;;
        --region)
            REGION=$2
            shift 2
            ;;
        -n|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --)
            shift
            break
            ;;
        *)
            echo "error: Unrecognized option \"$1\"" >&2
            exit 1
            ;;
    esac
done

if [ $# -lt 1 ]; then
    echo "error: BUCKET required" >&2
    exit 1
fi

BUCKET=$1
REGION=$2
OPTS=(
    --delete
    # Build timestamps are always updated during the build, so ignore them
    --size-only
)
if [ -n "$REGION" ]; then
    OPTS+=(--region "$REGION")
fi
if $DRY_RUN; then
   OPTS+=(--dryrun)
fi

echo "Syncing $BUILDDIR to $BUCKET"
aws s3 sync "${OPTS[@]}" "$BUILDDIR" "s3://${BUCKET}"
