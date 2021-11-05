#!/bin/bash

set -e

: ${PODMAN:=podman}
SRC=$(dirname "$0")

function usage() {
    cat <<EOF
Usage: $0 [OPTION]... BRANCH

  -h, --help		display this help and exit
EOF
}

ARGS=$(getopt -o h -l help -n "$0" -- "$@")
eval set -- "$ARGS"

while true; do
    case "$1" in
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


if [ -z "$1" ]; then
    echo "error: OS branch not specified" >&2
    exit 1
fi

BRANCH=$1

# Build the container
TAG="helpcenter:$BRANCH"
$PODMAN build --pull -t "$TAG" --build-arg "BRANCH=${BRANCH}" \
    -f "$SRC/Dockerfile-build" "$SRC"

# Build the docs in the container.
ABSSRC=$(readlink -f "$SRC")
$PODMAN run --rm -v "$ABSSRC:/src" -w /src "$TAG" ./generate-html-docs.sh
$PODMAN run --rm -v "$ABSSRC:/src" -w /src "$TAG" ./generate-index.py
