import argparse
import collections
import glob
import os
import re

from typing import Literal

import tabulate


class StraceTreePrinter:
    CHILD_PID_RE = r'^(clone|clone3|fork|vfork)\(.+?(\d+)$'
    COMMAND_RE = r'^execve\((.+?)\) = 0'
    EXIT_STATUS_RE = r'^(exit|exit_group)\((\d+)\)'

    INHERITED_MARK = '!'

    def __init__(self, *, root_path: str, prefix: str) -> None:
        self.root_path = root_path
        self.prefix = prefix

        self.argvs: dict[int, list[str]] = {}
        self.calls: dict[int, str] = {}
        self.child_pids: set[int] = set()
        self.childs: dict[int, list[int]] = collections.defaultdict(list)
        self.data: list[tuple[str, str, str, str, int | Literal['?'], str, str, int | Literal['?'], str]] = []
        self.envps: dict[int, list[str]] = {}
        self.exit_statuses: dict[int, int | Literal['?']] = {}
        self.first_entries: dict[int, str] = {}
        self.last_entries: dict[int, str] = {}
        self.parents: dict[int, int | Literal['?']] = {}
        self.pathnames: dict[int, str] = {}
        self.pids_that_wrote_to_stderr: set[int] = set()
        self.pids_that_wrote_to_stdout: set[int] = set()
        self.pids_with_missing_info: set[int] = set()
        self.pids: set[int] = set()

    def run(self) -> None:
        globbing_pathname = os.path.join(self.root_path, f'{self.prefix}.*')

        for file in glob.iglob(globbing_pathname):
            pid = int(file.split('.')[-1])

            self.pids.add(pid)

            with open(file) as f:
                for line in f:
                    timestamp, line = line.split(maxsplit=1)

                    if pid not in self.first_entries:
                        self.first_entries[pid] = timestamp

                    if line.startswith('write(1,'):
                        self.pids_that_wrote_to_stdout.add(pid)
                        continue

                    if line.startswith('write(2,'):
                        self.pids_that_wrote_to_stderr.add(pid)
                        continue

                    command_match = re.search(self.COMMAND_RE, line)
                    if command_match:
                        pathname, argv_envp = command_match[1].split(', ', maxsplit=1)
                        self.pathnames[pid] = pathname[1:-1]
                        self.argvs[pid], self.envps[pid] = self.parse_argv_envp(argv_envp)
                        continue

                    exit_status_match = re.search(self.EXIT_STATUS_RE, line)
                    if exit_status_match:
                        self.exit_statuses[pid] = int(exit_status_match[2])
                        continue

                    child_pid_match = re.search(self.CHILD_PID_RE, line)
                    if child_pid_match:
                        child_pid = int(child_pid_match[2])
                        self.childs[pid].append(child_pid)
                        self.parents[child_pid] = pid
                        self.calls[child_pid] = child_pid_match[1]
                        self.child_pids.add(child_pid)
                        continue

            if pid not in self.pathnames:
                self.pids_with_missing_info.add(pid)

            if pid not in self.exit_statuses:
                self.exit_statuses[pid] = '?'

            self.last_entries[pid] = timestamp

        root_pids = self.pids - self.child_pids

        if len(root_pids) != 1:
            raise Exception(f'Expected exactly one root pid: {root_pids}')

        self.root_pid = root_pids.pop()

        if self.root_pid in self.pathnames:
            self.calls[self.root_pid] = 'execve'
        else:
            # strace was run with --attach
            self.pathnames[self.root_pid] = '?'
            self.argvs[self.root_pid] = ['?']
            self.calls[self.root_pid] = '?'

        self.parents[self.root_pid] = '?'

    def print_table(self) -> None:
        for node in self.pids:
            self.add_missing_info(node)

        self.fill_table(self.root_pid)

        tabulate.PRESERVE_WHITESPACE = True
        tabulated_data = tabulate.tabulate(
            self.data,
            headers=[
                'Log',
                'Call',
                'First entry',
                'Last entry',
                'PPID',
                'Pathname',
                'Output',
                'Exit',
                'Argv',
            ]
        )
        tabulate.PRESERVE_WHITESPACE = False

        print(tabulated_data)

    def add_missing_info(self, node: int) -> None:
        elder_parent = self.find_elder_parent(node)
        self.pathnames[node] = self.pathnames[elder_parent]
        self.argvs[node] = self.argvs[elder_parent]

    def fill_table(self, node: int, level: int = 1) -> None:
        padding = ' ' * (level - 1) * 4

        exit_status = self.exit_statuses[node]

        log = f'{self.prefix}.{node}'

        call = self.calls[node]
        first_entry = self.first_entries[node]
        last_entry = self.last_entries[node]

        parent = self.parents[node]

        stdout = 'out' if node in self.pids_that_wrote_to_stdout else '   '
        stderr = 'err' if node in self.pids_that_wrote_to_stderr else '   '
        output = f'{stdout} {stderr}'

        pathname = self.pathnames[node]
        if node in self.pids_with_missing_info:
            pathname += f' {self.INHERITED_MARK}'

        argv = ' '.join(self.argvs[node])
        if node in self.pids_with_missing_info:
            argv += f' {self.INHERITED_MARK}'

        formatted_argv = padding + argv

        self.data.append(
            (
                log,
                call,
                first_entry,
                last_entry,
                parent,
                pathname,
                output,
                exit_status,
                formatted_argv,
            )
        )

        for child in self.childs[node]:
            self.fill_table(child, level=level + 1)

    def find_elder_parent(self, node: int) -> int:
        if self.parents[node] not in self.pids_with_missing_info and self.parents[node] in self.pathnames:
            return self.parents[node]
        else:
            return self.find_elder_parent(self.parents[node])

    @staticmethod
    def parse_argv_envp(line: str) -> tuple[list[str], list[str]]:
        ARGV_KEY = 'argv'
        ENVP_KEY = 'envp'

        data: dict[str, list[str]] = {
            ARGV_KEY: [],
            ENVP_KEY: [],
        }

        key = ARGV_KEY
        words = []
        skip_char = False
        reading_word = False

        word_chars: list[str] = []

        for char in line:
            if reading_word:
                if skip_char:
                    skip_char = False
                    word_chars.append(char)
                elif char == '\\':
                    skip_char = True
                elif char == '"':
                    reading_word = False
                    words.append(''.join(word_chars))
                else:
                    word_chars.append(char)
            else:
                if char == ']':
                    data[key] = words.copy()
                    key = ENVP_KEY
                    words.clear()
                elif char == '"':
                    reading_word = True
                    word_chars.clear()

        return data[ARGV_KEY], data[ENVP_KEY]

    def write_envp_files(self) -> None:
        for pid, envp in self.envps.items():
            with open(f'{pid}.envp', 'w') as f:
                for var in envp:
                    f.write(f'{var}\n')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--prefix', default='output')
    parser.add_argument('--root-path', default=os.getcwd())

    args = parser.parse_args()

    stp = StraceTreePrinter(prefix=args.prefix, root_path=args.root_path)
    stp.run()
    stp.write_envp_files()
    stp.print_table()

    return 0
