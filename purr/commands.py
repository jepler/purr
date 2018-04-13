# CircuitPython remote access
# Copyright © 2018 Jeff Epler <jepler@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import inspect
import functools
import contextlib
import logging

from .board import rstub_src

def remote(fun):
    src = None
    @functools.wraps(fun)
    def inner(purr, *args):
        nonlocal src
        if src is None:
            src = inspect.getsource(fun)
        startdef = src.find("def ")
        src = src[startdef:]
        return purr.send_purr_command('rfunc', fun.__name__, src, *args)
    return inner

@remote
def open(stub, filename, mode='rb'):
    global fd
    fd = open(filename, mode)

@remote
def close(stub):
    global fd
    fd.close()

@remote
def read(stub, count):
    return fd.read(count)

@remote
def write(stub, buf):
    return fd.write(buf)

@remote
def checksum(stub, filename, chunksize=256):
    try:
        import hashlib
    except:
        import uhashlib as hashlib
    try:
        import binascii
    except:
        import ubinascii as binascii
    import os
    try:
        os.stat(filename)
    except OSError:
        return None
    with open(filename, "rb") as f:
        sz = 0
        h = hashlib.sha256()
        while 1:
            block = f.read(chunksize)
            if not block: break
            sz += len(block)
            h.update(block)
        return sz, binascii.hexlify(h.digest())

@remote
def lsl(stub, location):
    S_IFDIR = 16384
    if not location.endswith("/"): location += "/"
    for o in os.listdir(location):
        st = os.stat(location + o)
        if st[0] == S_IFDIR:
            yield "{}/ - directory".format(o, st[6])
        else:
            yield "{} - {} bytes".format(o, st[6])

@contextlib.contextmanager
def purrfile(purr, filename, mode='rb'):
    open(purr, filename, mode)
    try:
        yield purr
    finally:
        close(purr)

def getfile(purr, filename, mode='rb', chunksize=256):
    blocks = []
    with purrfile(purr, filename, mode):
        while 1:
            block = read(purr, chunksize)
            if not block: break
            blocks.append(block)
    return type(blocks[0])().join(blocks)

def putfile(purr, filename, content, mode='wb', chunksize=256):
    with purrfile(purr, filename, mode):
        for i in range(0, len(content), chunksize):
            write(purr, content[i:i+chunksize])

def putstub(purr):
    putfile(purr, "/rstub.py", rstub_src)
