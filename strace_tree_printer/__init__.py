import argparse
import collections
import glob
import os
import re

import tabulate


tabulate.PRESERVE_WHITESPACE = True


class StraceTreePrinter:
    CHILD_PID_RE = r'^(clone|clone3|fork|vfork)\(.+?(\d+)$'
    COMMAND_RE = r'^execve\((.+?)\) = 0'
    EXIT_STATUS_RE = r'^(exit|exit_group)\((\d+)\)'

    INHERITED_MARK = '!'

    def __init__(self, *, root_path: str, prefix: str) -> None:
        self.root_path = root_path
        self.prefix = prefix

        self.argvs = {}
        self.child_calls = {}
        self.child_pids = set()
        self.childs = collections.defaultdict(list)
        self.data = []
        self.envps = {}
        self.exit_statuses = {}
        self.first_entries = {}
        self.last_entries = {}
        self.parents = {}
        self.pathnames = {}
        self.pids_that_wrote_to_stderr = set()
        self.pids_that_wrote_to_stdout = set()

    def run(self) -> None:
        pids = set()

        globbing_pathname = os.path.join(self.root_path, f'{self.prefix}.*')

        for file in glob.glob(globbing_pathname):
            pid = int(file.split('.')[-1])

            pids.add(pid)

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
                        self.child_calls[child_pid] = child_pid_match[1]
                        self.child_pids.add(child_pid)
                        continue

            self.last_entries[pid] = timestamp

        self.root_pid = (pids - self.child_pids).pop()

        if self.root_pid not in self.pathnames:
            # strace was run with --attach
            self.pathnames[self.root_pid] = '---'
            self.argvs[self.root_pid] = ['---']
            self.child_calls[self.root_pid] = '---'

        self.parents[self.root_pid] = '---'

        self.write_envp_files()
        self.fill_table(self.root_pid)

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

        print(tabulated_data)

    def fill_table(self, node: int, level: str = 0) -> None:
        if level == 0:
            padding = ''
        elif level == 1:
            padding = ' \\_ '
        else:
            padding = ' ' * (level - 1) * 4 + ' \\_ '

        exit_status = self.exit_statuses.get(node, '?')

        log = f'{self.prefix}.{node}'

        call = self.child_calls[node]
        first_entry = self.first_entries[node]
        last_entry = self.last_entries[node]

        stdout = 'out' if node in self.pids_that_wrote_to_stdout else '   '
        stderr = 'err' if node in self.pids_that_wrote_to_stderr else '   '
        output = f'{stdout} {stderr}'

        if node not in self.pathnames:
            elder_parent = self.find_elder_parent(node)

        if node in self.pathnames:
            pathname = self.pathnames[node]
        else:
            pathname = self.pathnames[elder_parent] + f' {self.INHERITED_MARK}'

        if node in self.argvs:
            argv = ' '.join(self.argvs[node])
        else:
            argv = ' '.join(self.argvs[elder_parent]) + f' {self.INHERITED_MARK}'

        formatted_argv = padding + argv

        self.data.append(
            (
                log,
                call,
                first_entry,
                last_entry,
                self.parents[node],
                pathname,
                output,
                exit_status,
                formatted_argv,
            )
        )

        for child in self.childs[node]:
            self.fill_table(child, level=level + 1)

    def find_elder_parent(self, node: int) -> int:
        if self.parents[node] in self.pathnames:
            return self.parents[node]
        else:
            return self.find_elder_parent(self.parents[node])

    @staticmethod
    def parse_argv_envp(line: str) -> tuple[list[str], list[str]]:
        data = []

        words = []
        skip_char = False
        reading_word = False

        for char in line:
            if reading_word:
                if skip_char:
                    skip_char = False
                    word += char
                elif char == '\\':
                    skip_char = True
                elif char == '"':
                    reading_word = False
                    words.append(word)
                else:
                    word += char
            else:
                if char == ']':
                    data.append(words.copy())
                    words.clear()
                elif char == '"':
                    reading_word = True
                    word = ''

        return data[0], data[1]

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

    return 0
