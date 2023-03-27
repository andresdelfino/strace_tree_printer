import argparse
import collections
import glob
import os
import re

import tabulate


tabulate.PRESERVE_WHITESPACE = True


class StraceTreePrinter:
    CHILD_PID_RE = r'^(clone|__clone2|clone3)\(.+?(\d+)$'
    COMMAND_RE = r'^execve\((.+?)\) = 0'
    EXIT_STATUS_RE = r'^exit_group\((\d+)\)'

    def __init__(self, *, root_path: str, prefix: str) -> None:
        self.root_path = root_path
        self.prefix = prefix

        self.childs = collections.defaultdict(list)
        self.pathnames = {}
        self.argvs = {}
        self.exit_statuses = {}
        self.data = []
        self.stdout = set()
        self.stderr = set()

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
                        pathname, argv_env = command_match[1].split(', ', maxsplit=1)
                        self.pathnames[pid] = pathname[1:-1]
                        self.argvs[pid] = ' '.join(self.parse_argv_env(argv_env)[0])
                        continue

                    exit_status_match = re.search(self.EXIT_STATUS_RE, line)
                    if exit_status_match:
                        self.exit_statuses[pid] = int(exit_status_match[1])
                        continue

                    child_pid_match = re.search(self.CHILD_PID_RE, line)
                    if child_pid_match:
                        child_pid = int(child_pid_match[2])
                        self.childs[pid].append(child_pid)
                        child_pids.add(child_pid)
                        continue

        root_pid = (pids - child_pids).pop()

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

        stdout = 'out' if node in self.stdout else '   '
        stderr = 'err' if node in self.stderr else '   '

        exit_status = self.exit_statuses.get(node, '?')
        if exit_status != 0:
            formatted_exit_status = f'\033[91m{exit_status}\033[0m'
        else:
            formatted_exit_status = exit_status

        log = f'{self.prefix}.{node}'
        pathname = self.pathnames.get(node, '?')
        output = f'{stdout} {stderr}'
        argv = padding + self.argvs.get(node, '?')

        self.data.append(
            (
                log,
                pathname,
                output,
                formatted_exit_status,
                argv,
            )
        )

        for child in self.childs[node]:
            self.fill_table(child, level=level + 1)

    def parse_argv_env(self, line: str) -> tuple[list[str], list[str]]:
        data = []

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
                if char == '[':
                    words = []
                elif char == ']':
                    data.append(words)
                    del words
                elif char == '"':
                    reading_word = True
                    word = ''

        return data[0], data[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--prefix', default='output')
    parser.add_argument('--root-path', default=os.getcwd())

    args = parser.parse_args()

    stp = StraceTreePrinter(prefix=args.prefix, root_path=args.root_path)
    stp.run()

    return 0
