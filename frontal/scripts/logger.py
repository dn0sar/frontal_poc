#!/usr/bin/env python3

#   This file is part of the Frontal attack PoC.
#
#   Copyright (C) 2020 Ivan Puddu <ivan.puddu@inf.ethz.ch>,
#                      Miro Haller <miro.haller@alumni.ethz.ch>,
#                      Moritz Schneider <moritz.schneider@inf.ethz.ch>
#
#   The Frontal attack PoC is free software: you can redistribute it
#   and/or modify it under the terms of the GNU General Public License
#   as published by the Free Software Foundation, either version 3 of
#   the License, or (at your option) any later version.
#
#   The Frontal attack PoC is distributed in the hope that it will
#   be useful, but WITHOUT ANY WARRANTY; without even the implied
#   warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#   See the GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with the Frontal attack PoC.
#   If not, see <http://www.gnu.org/licenses/>.
#
#   Short description of this file:
#   Logger class, providing fancy output printing and different log levels.
#

from colorama import Fore, Style
from enum import IntEnum
from sys import stderr


# Constants
TITLE_LINE_LEN  = 64
MAX_LINE_LENGTH = TITLE_LINE_LEN - 4
TITLE_SEP       = "#" * TITLE_LINE_LEN
INDENT_LEN      = 0

class LogLevel(IntEnum):
    SILENT  = 0
    NORMAL  = 1
    VERBOSE = 2

class Logger:
    def __init__(self, name, log_level=LogLevel.NORMAL):
        self.name       = f"[{name}]: "
        self.log_level  = log_level

    def set_verbose(self):
        self.log_level = LogLevel.VERBOSE

    def print_tagged(self, out, **kwargs):
        print(f"{self.name}" + out.replace("\n", f"\n{self.name}"), **kwargs)

    def error(self, msg, **kwargs):
        self.print_tagged(f"{Fore.RED}ERROR: {msg}{Style.RESET_ALL}",
                          file=stderr, **kwargs)
        exit(1)

    def warning(self, msg, **kwargs):
        if self.log_level > LogLevel.SILENT:
            self.print_tagged(f"{Fore.YELLOW}WARNING: {msg}{Style.RESET_ALL}",
                              file=stderr, **kwargs)

    def success(self, msg, **kwargs):
        if self.log_level > LogLevel.SILENT:
            self.print_tagged(f"{Fore.GREEN}SUCCESS: {msg}{Style.RESET_ALL}",
                              file=stderr, **kwargs)

    def title(self, title, **kwargs):
        if self.log_level > LogLevel.SILENT:
            self.print_tagged(TITLE_SEP, file=stderr)
            for i in range(0, len(title), MAX_LINE_LENGTH):
                content = title[i:i+MAX_LINE_LENGTH].center(MAX_LINE_LENGTH)
                self.print_tagged(f"# {content} #", file=stderr, **kwargs)
            self.print_tagged(TITLE_SEP, file=stderr)

    def line(self, line, **kwargs):
        if self.log_level > LogLevel.SILENT:
            indent = "#" * INDENT_LEN
            self.print_tagged(f"{indent} {line}", file=stderr, **kwargs)

    def debug(self, s, **kwargs):
        if self.log_level >= LogLevel.VERBOSE:
            self.print_tagged(f"[DEBUG]: {s}", file=stderr, **kwargs)

    def raw(self, s, **kwargs):
        print(s, **kwargs)
