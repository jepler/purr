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
from __future__ import absolute_import, print_function, division

import os
import logging
logging.basicConfig(level=os.environ.get("LOGLEVEL", "WARN"))

import click
import posixpath
import sys

from .board import purr_serial
import purr.commands as commands

board = None

@click.group()
@click.option('--port', '-p', envvar='PURR_PORT', required=True,
    type=click.STRING, help='''Serial port to use.  Can also specify via PURR_PORT environment variable''')
@click.option('--baud', '-b', default=115200, type=click.INT,
    help='''Baud rate''')
def cli(port, baud):
    global board
    board = purr_serial(port, baud)

def local_checksum(filename):
    print("local_checksum", filename)
    import hashlib
    if not os.access(filename, os.F_OK): return None
    with open(filename, 'rb') as f:
        content = f.read()
    return (len(content), hashlib.sha256(content).hexdigest().encode('utf-8'))

@cli.command()
@click.option('--skip-checksum', is_flag=True, help='Do not check for matching checksum')
@click.argument('remote_file')
@click.argument('local_file', required=False)
def get(remote_file, local_file=None, skip_checksum=True):
    print("get", remote_file, local_file, skip_checksum)
    if local_file is None: local_file = posixpath.split(remote_file)[-1]
    print("get", remote_file, local_file, skip_checksum)
    if not skip_checksum:
        c1 = local_checksum(local_file)
        c2 = commands.checksum(board, remote_file)
        if c1 == c2:
            logging.info("Checksum match")
            return
    contents = commands.getfile(board, remote_file)
    with open(local_file, "wb") as f: f.write(contents)
    logging.info("Transferred %d bytes", len(contents))

@cli.command()
@click.argument('remote_file')
def cat(remote_file):
    contents = commands.getfile(board, remote_file)
    sys.stdout.buffer.write(contents)

@cli.command()
@click.argument('remote_file')
def rcat(remote_file):
    contents = sys.stdin.buffer.read()
    commands.putfile(board, remote_file, contents)

@cli.command()
@click.argument('remote_file')
def checksum(remote_file):
    print("{} {}".format(commands.checksum(board, remote_file)[1].decode('ascii', 'replace'), remote_file))

@cli.command()
def upload_stub():
    commands.putstub(board)

@cli.command()
@click.option('--skip-checksum', is_flag=True, help='Do not check for matching checksum')
@click.argument('local_file')
@click.argument('remote_file', required=False)
def put(local_file, remote_file=None, skip_checksum=False):
    if remote_file is None: remote_file = os.path.split(local_file)[-1]
    if not skip_checksum:
        c1 = local_checksum(local_file)
        c2 = commands.checksum(board, remote_file)
        if c1 == c2:
            logging.info("Checksum match")
            return
    with open(local_file, "rb") as f: contents = f.read()
    commands.putfile(board, remote_file, contents)

@cli.command()
@click.option('-l', '--long', is_flag=True, help='Show file size (not POSIX ls compatible')
@click.argument('directory', required=False, default='/')
def ls(directory='/', long=False):
    if long:
        rows = commands.lsl(board, directory)
    else:
        rows = board.send_purr_command('os.listdir', directory)
    for r in rows: print(r)

@cli.command()
@click.argument('remote_file')
def rm(remote_file):
    board.send_purr_command('os.unlink', remote_file)

@cli.command()
@click.argument('remote_dir')
def rmdir(remote_dir):
    board.send_purr_command('os.rmdir', remote_dir)

@cli.command()
@click.argument('remote_dir')
def mkdir(remote_dir):
    board.send_purr_command('os.mkdir', remote_dir)

if __name__ == '__main__':
    cli()
