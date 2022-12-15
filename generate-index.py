#!/usr/bin/python3

# Generate an index page from the directories of generated HTML.

from argparse import ArgumentParser
import gi
import os
import jinja2
import sys

gi.require_version('GnomeDesktop', '3.0')
from gi.repository import GnomeDesktop  # noqa: E402

SRCDIR = os.path.dirname(__file__)
DEFAULT_BUILDDIR = os.path.join(SRCDIR, 'build')

ap = ArgumentParser(description='Generate helpcenter index page')
ap.add_argument('-d', '--builddir', metavar='DIR', default=DEFAULT_BUILDDIR,
                help=(f'path to HTML build directory '
                      f'(default: {DEFAULT_BUILDDIR})'))
ap.add_argument('-b', '--branch', help='build in BRANCH subdirectory')
ap.add_argument('-f', '--force', action='store_true',
                help='overwrite existing index.html')
ap.add_argument('-n', '--dry-run', action='store_true',
                help='only show the generated HTML')
args = ap.parse_args()

if args.branch:
    args.builddir = os.path.join(args.builddir, args.branch)
index_path = os.path.join(args.builddir, 'index.html')
if not (args.dry_run or args.force) and os.path.exists(index_path):
    print(f'error: {index_path} already exists', file=sys.stderr)
    sys.exit(1)

catalogs = []
for entry in os.listdir(args.builddir):
    if entry in ('css', 'img', 'index.html'):
        continue

    locale = entry

    # Rename C to en since C is only relevant to locale nerds and not
    # the general public
    if locale == 'C':
        locale = 'en'

    # For a full locale without a specified charset, the default charset
    # for that locale will be used. However, gnome-desktop assumes UTF-8
    # is normal and suffixes the charset. Set the charset to .utf8 so
    # that doesn't happen.
    if '_' in locale:
        locale += '.utf8'

    language = GnomeDesktop.get_language_from_locale(locale)
    catalogs.append((language, entry))

# Sort by language
catalogs.sort()

# Now render the template
loader = jinja2.FileSystemLoader(SRCDIR)
env = jinja2.Environment(loader=loader)
template = env.get_template('index.html')
index = template.render(catalogs=catalogs)
if args.dry_run:
    print(index)
else:
    with open(index_path, 'w') as f:
        f.write(index)
