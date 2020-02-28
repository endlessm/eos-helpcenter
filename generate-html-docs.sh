#!/bin/bash -e

XSL=/build/endless-customizations.xsl
DEST=/build/html

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
Usage: $0 [OPTION]... SRC XSL DEST

  -h, --help        display this help and exit
EOF
}

ARGS=$(getopt -o o:x:h -l outdir:,xsl:,help -n "$0" -- "$@")
eval set -- "$ARGS"

while true; do
    case "$1" in
	-o|--outdir)
	    DEST=$2
	    shift 2
	    ;;
	-x|--xsl)
	    XSL=$2
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

yelp-build --help >/dev/null 2>&1 || show_need_yelp

echo ""
echo "  Endless OS Doc2HTML script"
echo ""

# XSLT path for finding Endless yelp-xsl components
xslt_path=/usr/share/yelp-xsl/xslt/common/domains

# Start generating documentation
echo "  Generating documentation in $DEST..."
for doc_path in /usr/share/help/*/gnome-help; do

    lang=$(basename $(dirname "$doc_path"))
    doc_out="$DEST/$lang"

    mkdir -p "$doc_out"

    echo -n "      $lang..."

    yelp-build html -o "$doc_out" -x "$XSL" -p "$xslt_path" \
        "$doc_path"/*.page

    echo " OK"

done

# Copy the Endless CSS and images to root
echo "  Including assets in $DEST..."
for asset in css img; do
    echo -n "      $asset..."
    cp -r /usr/share/yelp/endless/"$asset" "$DEST"
    echo " OK"
done

echo ""
echo "  Finished. Documentation is in html/ folder."
echo ""
