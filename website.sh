#!/bin/bash

# Run the website in an nginx container.

set -e

: "${DOCKER:=docker}"

SRCDIR=$(dirname "$0")
BUILDDIR="$SRCDIR/build"
PORT=8080

usage() {
    cat <<EOF
Usage: $0 [OPTION...] BUILDDIR
Run website in an nginx container.

  -p, --port PORT	HTTP port to expose (default: $PORT)
  -h, --help		show this message and exit

Additional options can be passed to docker run after a -- option. By default,
docker is used, but this can be changed through the DOCKER environment
variable.
EOF
}

ARGS=$(getopt -n "$0" -o p:h -l port,help -- "$@")
eval set -- "$ARGS"

while true; do
    case "$1" in
        -p|--port)
            PORT=$2
            shift 2
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

[ -n "$1" ] && BUILDDIR="$1"

if ! [ -d "$BUILDDIR" ]; then
    echo "error: $BUILDDIR does not exist" >&2
    exit 1
fi

srcdir=$(readlink -f "$SRCDIR")
builddir=$(readlink -f "$BUILDDIR")
confdir=/etc/nginx/conf.d
htmldir=/usr/share/nginx/html

echo "Running website at http://localhost:$PORT"
exec $DOCKER run \
    -p "$PORT:80" \
    -v "$srcdir/nginx-no-cache.conf:$confdir/no-cache.conf:ro" \
    -v "$builddir:$htmldir:ro" \
    "$@" \
    nginx:stable
