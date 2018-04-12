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

from setuptools import *

setup(
    name='purr',
    version='0',

    author='Jeff Epler',
    author_email='jepler@gmail.com',

    description='Python modules for remote access to CircuitPython boards over serial connection',
    url='https://github.com/jepler/purr',
    license='GPL3',

    classifiers=[
        'Development Status :: 1 - Planning',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3',
        'Topic :: Communications',
        'Topic :: Software Development :: Embedded Systems',
    ],
    keywords='circuitpython',

    packages=find_packages(),
    install_requires=['click', 'pyserial'],
    entry_points={'console_scripts': ['purr=purr.cli:cli']}
)

