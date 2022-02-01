#!/bin/bash -e

SRCDIR=$(dirname "$0")
DEST="$SRCDIR/build"
XSL="$SRCDIR/build.xsl"

function show_need_yelp() {
    echo "  ERROR: this script requires 'yelp-build'"
    echo ""
    echo "  To install it, you need:"
    echo "      - A converted system (run '$ sudo eos-convert-system && sudo reboot now')"
    echo "      - yelp-tools package (run '$ sudo apt-get update && sudo apt-get -y install yelp-tools')"
    echo ""

    exit 1
}

function usage() {
    cat <<EOF
Usage: $0 [OPTION]... SRC DEST

  -h, --help        display this help and exit
EOF
}

ARGS=$(getopt -o o:h -l outdir:,help -n "$0" -- "$@")
eval set -- "$ARGS"

while true; do
    case "$1" in
	-o|--outdir)
	    DEST=$2
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
    esac
done

command -v yelp-build >/dev/null 2>&1 || show_need_yelp

echo ""
echo "  Endless OS Doc2HTML script"
echo ""

# Delete existing build directory
if [ -d "$DEST" ]; then
    echo "  Deleting existing documentation in $DEST"
    rm -rf "$DEST"
fi

# Start generating documentation
echo "  Generating documentation in $DEST..."
for doc_path in /usr/share/help/*/gnome-help; do

    lang=$(basename $(dirname "$doc_path"))
    doc_out="$DEST/$lang"

    mkdir -p "$doc_out"

    echo -n "      $lang..."

    yelp-build html -o "$doc_out" -x "$XSL" "$doc_path"/*.page

    echo " OK"

done

echo ""
echo "  Finished. Documentation is in $DEST folder."
echo ""
