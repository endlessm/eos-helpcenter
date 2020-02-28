#!/usr/bin/python3 -u

# Build help center docs from EOS packages
#
# Copyright (C) 2017  Endless Mobile, Inc.
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

import apt
import apt_pkg
from argparse import ArgumentParser
import datetime
import os
import shutil
import subprocess
import sys


HELPCENTER_DIR = '/srv/helpcenter'
HELPCENTER_HTTP_LINK = '/srv/helpcenter/www'
CACHE_DIR = os.path.join(HELPCENTER_DIR, 'cache')
KEYRING = os.path.join(HELPCENTER_DIR, 'eos-archive-keyring.gpg')
BUILDROOT_DIR = os.path.join(HELPCENTER_DIR, 'root')
ARCH = apt_pkg.get_architectures()[0]
MIRROR = 'http://obs-master.endlessm-sf.com:82/shared/eos'
BRANCH = 'eos3'
COMPONENTS = ('core', 'endless')
PACKAGES = {
    # dbus-user-session is only a dependency of other packages, but
    # debootstrap's resolver is not capable of resolving the
    # required dbus-session-bus virtual package on its own
    'dbus-user-session',
    'gnome-getting-started-docs',
    'gnome-user-guide',
    'yelp',
    'yelp-tools',
    'yelp-xsl',
}
HELPCENTER_SCRIPT = os.path.join(HELPCENTER_DIR, 'generate-html-docs.sh')
HELPCENTER_XSL = os.path.join(HELPCENTER_DIR, 'endless-customizations.xsl')


# Initialize apt
apt_pkg.init()


def umount_all(root):
    """Unmount all filesystems under root"""
    root = os.path.realpath(root)
    if not os.path.exists(root):
        return

    # Re-read the mount table after every unmount in case there are
    # aliased mounts
    while True:
        path = None
        with open('/proc/self/mountinfo') as f:
            mounts = f.readlines()

        # Read the mounts backwards to unmount submounts first
        for line in reversed(mounts):
            fields = line.split()
            if len(fields) < 5:
                continue
            target = fields[4]
            if target == root or target.startswith(root + '/'):
                path = target
                break

        if path is None:
            # No more paths to unmount
            return

        print('Unmounting', path)
        subprocess.check_call(['umount', path])



def umount_all(root):
    """Unmount all filesystems under root"""
    root = os.path.realpath(root)
    if not os.path.exists(root):
        return

    # Re-read the mount table after every unmount in case there are
    # aliased mounts
    while True:
        path = None
        with open('/proc/self/mountinfo') as f:
            mounts = f.readlines()

        # Read the mounts backwards to unmount submounts first
        for line in reversed(mounts):
            fields = line.split()
            if len(fields) < 5:
                continue
            target = fields[4]
            if target == root or target.startswith(root + '/'):
                path = target
                break

        if path is None:
            # No more paths to unmount
            return

        print('Unmounting', path)
        subprocess.check_call(['umount', path])


def disk_usage(path):
    """Recursively gather disk usage in bytes for path"""
    total = os.stat(path, follow_symlinks=False).st_size
    for root, dirs, files in os.walk(path):
        total += sum([os.stat(os.path.join(root, name),
                              follow_symlinks=False).st_size
                      for name in dirs + files])
        return total


class DocsError(Exception):
    """Errors from docs build"""
    def __init__(self, *args):
        self.msg = ' '.join(map(str, args))

    def __str__(self):
        return str(self.msg)


class DocsPkgCache(object):
    """Cache for docs build packages

    A temporary Apt cache directory for keeping track of what versions
    have been used in the previous build and what builds are
    available.

    """

    APT_NEEDED_DIRS = (
        'etc/apt/apt.conf.d',
        'etc/apt/preferences.d',
        'etc/apt/trusted.gpg.d',
        'var/lib/apt/lists/partial',
        'var/cache/apt/archives/partial',
        'var/lib/dpkg',
    )

    # Maximum size of the cache directory (1 GB)
    MAX_SIZE = 2 ** 30

    def __init__(self, cache_dir=CACHE_DIR):
        self.cache_dir = cache_dir

        if os.path.exists(self.cache_dir) and \
           disk_usage(self.cache_dir) > self.MAX_SIZE:
            print('Removing', self.cache_dir,
                  'since disk usage exceeds', self.MAX_SIZE, 'bytes')
            shutil.rmtree(self.cache_dir)

        for subdir in self.APT_NEEDED_DIRS:
            os.makedirs(os.path.join(self.cache_dir, subdir),
                        exist_ok=True)

        # Create sources.list
        sources_list = os.path.join(self.cache_dir,
                                    'etc/apt/sources.list')
        with open(sources_list, 'w') as f:
            f.write('deb {} {} {}\n'.format(MIRROR, BRANCH,
                                            ' '.join(COMPONENTS)))

        # Copy ~/.netrc to /etc/apt/auth.conf if exists
        netrc = os.path.expanduser('~/.netrc')
        auth_conf = os.path.join(self.cache_dir, 'etc/apt/auth.conf')
        if os.path.exists(netrc):
            shutil.copy2(netrc, auth_conf)

        # Create an empty dpkg status if it doesn't exist
        self.dpkg_status = os.path.join(self.cache_dir,
                                        'var/lib/dpkg/status')
        if not os.path.exists(self.dpkg_status):
            with open(self.dpkg_status, 'w'):
                pass

        # Configure apt
        apt_pkg.config.set('Dir', self.cache_dir)
        apt_pkg.config.set('Dir::State::status', self.dpkg_status)

        # Single arch only
        apt_pkg.config.set('APT::Architecture', ARCH)
        apt_pkg.config.set('APT::Architectures', ARCH)

        if os.path.exists(KEYRING):
            apt_pkg.config.set('Dir::Etc::trusted', KEYRING)

        self.progress = \
            apt.progress.text.AcquireProgress(outfile=sys.stderr)

        self.cache = apt.Cache()
        self._setup_filter()

    def update(self):
        self.cache.update(self.progress)
        self.cache.open()
        self._setup_filter()

    # Filter for packages used in docs build
    class DocsPkgFilter(apt.cache.Filter):
        def apply(self, pkg):
            return pkg.shortname in PACKAGES

    def _setup_filter(self):
        self.docs_pkgs = apt.cache.FilteredCache(self.cache)
        self.docs_pkgs.set_filter(self.DocsPkgFilter())

    def build_packages(self):
        pkgs = {}
        for name in PACKAGES:
            version = None
            if name in self.docs_pkgs:
                pkg = self.docs_pkgs[name]
                if pkg.is_installed:
                    version = pkg.installed.version
            pkgs[name] = version
        return pkgs

    def available_packages(self):
        pkgs = {}
        for name in PACKAGES:
            version = None
            if name in self.docs_pkgs:
                pkg = self.docs_pkgs[name]
                version = pkg.candidate.version
            pkgs[name] = version
        return pkgs


class DocsBuildRoot(object):
    """Build root for the docs build

    A build root generated with debootstrap containing all the
    packages for the target EOS version.
    """

    def __init__(self, root_dir=BUILDROOT_DIR, archives_dir=None):
        self.root_dir = BUILDROOT_DIR
        self.archives_src = archives_dir
        self.archives_dst = os.path.join(self.root_dir,
                                         'var/cache/apt/archives')
        self._archives_mount = None

    def clean(self):
        if not os.path.exists(self.root_dir):
            return

        # Unmount anything under root
        umount_all(self.root_dir)

        print('Removing existing', self.root_dir)
        shutil.rmtree(self.root_dir)

    def mount_archives(self):
        if self.archives_src is not None:
            target = os.path.join(self.root_dir,
                                  'var/cache/apt/archives')
            os.makedirs(self.archives_dst)
            print('Mounting', self.archives_src, 'at',
                  self.archives_dst)
            subprocess.check_call(['mount', '--bind', self.archives_src,
                                   self.archives_dst])
            self._archives_mount = self.archives_dst

    def unmount_archives(self):
        if self._archives_mount is not None:
            print('Unmounting', self._archives_mount)
            subprocess.check_call(['umount', self._archives_mount])

    def create(self):
        cmd = ['debootstrap',
               '--variant=minbase',
               '--include=' + ','.join(PACKAGES),
               '--components=' + ','.join(COMPONENTS),
               '--keyring=' + KEYRING,
               BRANCH,
               self.root_dir,
               MIRROR,
               '/usr/share/debootstrap/scripts/sid']
        print('Creating build root', self.root_dir)
        print('$', *cmd)
        subprocess.check_call(cmd)

    def __enter__(self):
        self.clean()
        self.mount_archives()
        return self

    def __exit__(self, exc, value, tb):
        self.unmount_archives()


class DocsBuild(object):
    """Documentation builder

    Actual documentation build using yelp-tools in a build root.
    """

    CHROOT_FILESYSTEMS = ('/proc', '/sys', '/dev/pts')

    def __init__(self, root_dir=BUILDROOT_DIR):
        self.root_dir = BUILDROOT_DIR
        self.build_dir = os.path.join(self.root_dir, 'build')
        self.output_dir = os.path.join(self.build_dir, 'html')
        self._mounts = []

        if not os.path.isdir(self.root_dir):
            raise DocsError('No build root found at', self.root_dir)

        umount_all(self.root_dir)

        # Recreate the build directory
        if os.path.exists(self.build_dir):
            print('Removing existing', self.build_dir)
            shutil.rmtree(self.build_dir)
        os.makedirs(self.build_dir)

        # Copy in the script and XSL
        for src in (HELPCENTER_SCRIPT, HELPCENTER_XSL):
            dest = os.path.join(self.build_dir, os.path.basename(src))
            print('Copying', src, 'to', dest)
            shutil.copy2(src, dest)

    def mount_filesystems(self):
        if len(self._mounts) > 0:
            raise DocsError('Filesystems already mounted in',
                            self.root_dir)
        for src in self.CHROOT_FILESYSTEMS:
            dest = os.path.join(self.root_dir, src[1:])
            print('Mounting', src, 'at', dest)
            os.makedirs(dest, exist_ok=True)
            subprocess.check_call(['mount', '--bind', src, dest])
            self._mounts.append(dest)

    def unmount_filesystems(self):
        for target in reversed(self._mounts):
            print('Unmounting', target)
            subprocess.check_call(['umount', target])
            self._mounts.pop()

    def build(self):
        script = os.path.join('/build', os.path.basename(HELPCENTER_SCRIPT))
        cmd = ['chroot', self.root_dir, script]
        print('Building documentation in', self.root_dir)
        print('$', *cmd)
        subprocess.check_call(cmd)

    def __enter__(self):
        self.mount_filesystems()
        return self

    def __exit__(self, exc, value, tb):
        self.unmount_filesystems()


def main():
    aparser = ArgumentParser(description='Build helpcenter docs')
    aparser.add_argument('-f', '--force', action='store_true',
                         help='force build even if no changes')
    args = aparser.parse_args()

    pkgcache = DocsPkgCache()
    pkgcache.update()
    build_packages = pkgcache.build_packages()
    available_packages = pkgcache.available_packages()
    print('Packages used in previous build:')
    for package, version in sorted(build_packages.items()):
        print(' {}: {}'.format(package, version))
    print('Packages available for build:')
    for package, version in sorted(available_packages.items()):
        print(' {}: {}'.format(package, version))

    if build_packages == available_packages:
        print('Packages from previous build match available packages')
        if args.force:
            print('Continuing build as requested')
        else:
            print('All done')
            return

    # Use the cached archives directory to keep packages between runs
    archives = os.path.join(pkgcache.cache_dir,
                            'var/cache/apt/archives')
    with DocsBuildRoot(archives_dir=archives) as root:
        root.create()

    with DocsBuild() as build:
        outdir = build.output_dir
        build.build()

    # Move the generated docs out to a versioned directory
    now = datetime.datetime.now()
    cur = os.path.join(HELPCENTER_DIR,
                       'helpcenter-' + now.strftime('%Y%m%d-%H%M%S'))
    print('Moving', outdir, 'to', cur)
    os.rename(outdir, cur)

    # Replace the http symlink
    prev = None
    if os.path.exists(HELPCENTER_HTTP_LINK):
        if not os.path.islink(HELPCENTER_HTTP_LINK):
            raise DocsError(HELPCENTER_HTTP_LINK, 'is not a symlink')
        prev = os.path.realpath(HELPCENTER_HTTP_LINK)
    target = os.path.relpath(cur, os.path.dirname(HELPCENTER_HTTP_LINK))
    print('Setting symlink', HELPCENTER_HTTP_LINK, 'to', target)
    os.symlink(target, HELPCENTER_HTTP_LINK + '.new')
    os.rename(HELPCENTER_HTTP_LINK + '.new', HELPCENTER_HTTP_LINK)
    if prev is not None:
        print('Removing previous build', prev)
        if os.path.isdir(prev):
            shutil.rmtree(prev)
        else:
            os.unlink(prev)

    # Copy the buildroot dpkg status to the cache to represent the
    # current build
    src = os.path.join(BUILDROOT_DIR, 'var/lib/dpkg/status')
    dst = os.path.join(CACHE_DIR, 'var/lib/dpkg/status')
    print('Copying', src, 'to', dst)
    shutil.copy2(src, dst)

    # Cleanup the build root
    print('Removing', BUILDROOT_DIR)
    shutil.rmtree(BUILDROOT_DIR)

    print('All done')


if __name__ == '__main__':
    main()
