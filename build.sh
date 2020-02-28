#!/bin/bash

# Copyright (C) 2020  Endless Mobile, Inc.
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

# Generate the helpcenter docs in a checkout of the latest stable OS.

set -e

SRCDIR=$(dirname "$0")
BRANCH=eos3a
ARCH=$(dpkg --print-architecture 2>/dev/null || echo amd64)
HOST=https://ostree.endlessm.com
FORCE=false
OUTDIR="$SRCDIR"

usage() {
    cat <<EOF
Usage: $0 [OPTION...]
Generate helpcenter HTML in OSTree checkout

  -b, --branch	OS branch to checkout (default: $BRANCH)
  -a, --arch	OS architecture to checkout (default: $ARCH)
  -H, --host	OSTree remote host (default: $HOST)
  -o, --outdir  output directory (default: $OUTDIR)
  -f, --force	force build even if OSTree commit hasn't changed
  --debug	enable debugging messages
  -h, --help	display this message
EOF
}

ARGS=$(getopt -n "$0" \
              -o b:a:H:o:fh \
              -l branch:,arch:,host:,outdir:,force,debug,help \
              -- "$@")
eval set -- "$ARGS"

while true; do
    case "$1" in
        -b|--branch)
            BRANCH=$2
            shift 2
            ;;
        -a|--arch)
            ARCH=$2
            shift 2
            ;;
        -H|--host)
            HOST=$2
            shift 2
            ;;
        -o|--outdir)
            OUTDIR=$2
            shift 2
            ;;
        -f|--force)
            FORCE=true
            shift
            ;;
        --debug)
            set -x
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

REPO="$OUTDIR/repo"
CHECKOUT="$OUTDIR/checkout"
VAR="$OUTDIR/var"
BUILD="$OUTDIR/build"
ARCHIVE="$OUTDIR/html.tar.gz"
MANIFEST="$OUTDIR/manifest.json"

REF="os/eos/$ARCH/$BRANCH"
REMOTE=eos
REMOTE_REPO="ostree/eos-$ARCH"
REMOTE_URL="$HOST/$REMOTE_REPO"
echo "Initializing OSTree repo $REPO"
ostree --repo="$REPO" init --mode=bare-user
echo "Adding OSTree remote $REMOTE $REMOTE_URL"
ostree --repo="$REPO" remote add --if-not-exists "$REMOTE" "$REMOTE_URL"

echo "Pulling OSTree ref $REMOTE:$REF"
ostree --repo="$REPO" pull "$REMOTE" "$REF"

cur_commit=$(ostree --repo="$REPO" rev-parse "$REMOTE:$REF")
cur_version=$(ostree --repo="$REPO" show --print-metadata-key=version \
                     "$REMOTE:$REF" | sed "s/'//g")
echo "Current build:"
echo "  ref: $REF"
echo "  commit: $cur_commit"
echo "  version: $cur_version"
if [ -f "$MANIFEST" ] && [ -f "$ARCHIVE" ]; then
    prev_ref=$(jq -r .ref "$MANIFEST")
    prev_commit=$(jq -r .commit "$MANIFEST")
    prev_version=$(jq -r .version "$MANIFEST")
    echo "Previous build:"
    echo "  ref: $prev_ref"
    echo "  commit: $prev_commit"
    echo "  version: $prev_version"
    if [ "$prev_ref" = "$REF" ] && [ "$prev_commit" = "$cur_commit" ]; then
        echo "No changes from previous build"
        if $FORCE; then
            echo "Forcing build"
        else
            exit 0
        fi
    fi
fi

echo "Checking out OSTree ref $REMOTE:$REF to $CHECKOUT"
rm -rf "$CHECKOUT"
ostree --repo="$REPO" checkout -U "$REMOTE:$REF" "$CHECKOUT"

echo "Populating $VAR from $CHECKOUT/var"
rm -rf "$VAR"
cp -a "$CHECKOUT/var" "$VAR"

# We're going to install packages, so break the /var/lib/dpkg symlink
if [ -L "$VAR/lib/dpkg" ]; then
    rm -f "$VAR/lib/dpkg"
    cp -pHR "$CHECKOUT/var/lib/dpkg" "$VAR/lib"
fi

# Populate /etc like ostree deploy would do
if [ -d "$CHECKOUT/etc" ]; then
    echo "error: /etc already exists in $CHECKOUT" >&2
    exit 1
fi
echo "Populating $CHECKOUT/etc"
cp -a "$CHECKOUT/usr/etc" "$CHECKOUT/etc"

# General options for bubblewrap
BWRAP_OPTS=(
    --bind "$CHECKOUT" /
    --bind "$VAR" /var
    --proc /proc
    --dev /dev
    --tmpfs /tmp
    --tmpfs /run
    --ro-bind /etc/resolv.conf /etc/resolv.conf
)

# Running as root with bwrap
BWRAP_ROOT_OPTS=(
    "${BWRAP_OPTS[@]}"
    --unshare-user
    --uid 0
    --gid 0
)

# Running the docs build under bwrap
BWRAP_BUILD_OPTS=(
    "${BWRAP_OPTS[@]}"
    --bind "$BUILD" /build
)

# APT options for running under bwrap
APT_OPTS=(
    # Need to tell apt not to change users when downloading or
    # installing packages since that won't work in bwrap.
    -o APT::Sandbox::User=
)

# Packages to install in the checkout for the build
BUILD_PKGS=(
    gir1.2-gnomedesktop-3.0
    python3-gi
    python3-jinja2
    yelp-tools
)

echo "Installing ${BUILD_PKGS[*]} in $CHECKOUT"
bwrap "${BWRAP_OPTS[@]}" \
      apt-get "${APT_OPTS[@]}" update
bwrap "${BWRAP_ROOT_OPTS[@]}" \
      apt-get "${APT_OPTS[@]}" -y install "${BUILD_PKGS[@]}"

BUILD_FILES=(
    "$SRCDIR"/endless-customizations.xsl
    "$SRCDIR"/generate-html-docs.sh
    "$SRCDIR"/generate-index.py
    "$SRCDIR"/index.html
)
rm -rf "$BUILD"
mkdir "$BUILD"
echo "Populating $BUILD"
cp -a "${BUILD_FILES[@]}" "$BUILD"

echo "Generating HTML documentation"
bwrap "${BWRAP_BUILD_OPTS[@]}" /build/generate-html-docs.sh

echo "Generating HTML index"
bwrap "${BWRAP_BUILD_OPTS[@]}" /build/generate-index.py

# We want to make the tarball files owned by root:root instead of the
# random UID this script is running as.
echo "Generating HTML archive $ARCHIVE"
tar -cz -C "$BUILD" -f "$ARCHIVE" --owner=0 --group=0 html

echo "Generating $MANIFEST"
cat > "$MANIFEST" <<EOF
{
  "ref": "$REF",
  "commit": "$cur_commit",
  "version": "$cur_version"
}
EOF
