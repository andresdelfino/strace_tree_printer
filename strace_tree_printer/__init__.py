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

    def __init__(self, *, root_path: str, prefix: str, format_exit_status: bool) -> None:
        self.root_path = root_path
        self.prefix = prefix
        self.format_exit_status = format_exit_status

        self.argvs = {}
        self.childs = collections.defaultdict(list)
        self.data = []
        self.envps = {}
        self.exit_statuses = {}
        self.parents = {}
        self.pathnames = {}
        self.stderr = set()
        self.stdout = set()

    def run(self) -> None:
        pids = set()
        child_pids = set()

        globbing_pathname = os.path.join(self.root_path, f'{self.prefix}.*')

        for file in glob.glob(globbing_pathname):
            pid = int(file.split('.')[-1])
            pids.add(pid)

            with open(file) as f:
                for line in f:
                    line = line.split(maxsplit=1)[1]

                    if line.startswith('write(1,'):
                        self.stdout.add(pid)
                        continue

                    if line.startswith('write(2,'):
                        self.stderr.add(pid)
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
                        child_pids.add(child_pid)
                        continue

        root_pid = (pids - child_pids).pop()

        self.write_envp_files()
        self.fill_table(root_pid)

        tabulated_data = tabulate.tabulate(
            self.data,
            headers=[
                'Log',
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
        if exit_status != 0 and self.format_exit_status:
            formatted_exit_status = f'\033[91m{exit_status}\033[0m'
        else:
            formatted_exit_status = exit_status

        log = f'{self.prefix}.{node}'

        if node in self.pathnames:
            pathname = self.pathnames[node]
        else:
            pathname = self.pathnames[self.parent[node]]

        stdout = 'out' if node in self.stdout else '   '
        stderr = 'err' if node in self.stderr else '   '
        output = f'{stdout} {stderr}'

        if node in self.argvs:
            argv = ' '.join(self.argvs[node])
        else:
            argv = ' '.join(self.argvs[self.parent[node]])

        formatted_argv = padding + argv

        self.data.append(
            (
                log,
                pathname,
                output,
                formatted_exit_status,
                formatted_argv,
            )
        )

        for child in self.childs[node]:
            self.fill_table(child, level=level + 1)

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
    parser.add_argument('--format-exit-status', action='store_true')
    parser.add_argument('--prefix', default='output')
    parser.add_argument('--root-path', default=os.getcwd())

    args = parser.parse_args()

    stp = StraceTreePrinter(prefix=args.prefix, root_path=args.root_path, format_exit_status=args.format_exit_status)
    stp.run()

    return 0
