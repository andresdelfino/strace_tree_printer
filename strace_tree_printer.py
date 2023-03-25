import collections
import glob
import os
import re

import tabulate


tabulate.PRESERVE_WHITESPACE = True


class StraceTreePrinter:
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

                    command_match = re.search(r'^execve\(([^]]+\]).+= 0', line)
                    if command_match:
                        pathname, argv = command_match[1].split(', ', maxsplit=1)
                        self.pathnames[pid] = pathname[1:-1]
                        self.argvs[pid] = argv[2:-2].replace('", "', ' ')
                        continue

                    exit_status_match = re.search(r'^exit_group\((\d+)\)', line)
                    if exit_status_match:
                        self.exit_statuses[pid] = int(exit_status_match[1])
                        continue

                    child_pid_match = re.search(r'^(clone|__clone2|clone3)\(.+?(\d+)$', line)
                    if child_pid_match:
                        child_pid = int(child_pid_match[2])
                        self.childs[pid].append(child_pid)
                        child_pids.add(child_pid)
                        continue

        root_pid = (pids - child_pids).pop()

        self.fill_table(root_pid)

        tabulated_data = tabulate.tabulate(self.data, headers=['Filename', 'Pathname', 'stdout', 'stderr', 'Exit status', 'Argv'])

        print(tabulated_data)

    def fill_table(self, node: int, level: str = 0) -> None:
        if level == 0:
            padding = ''
        elif level == 1:
            padding = ' \\_ '
        else:
            padding = ' ' * (level - 1) * 4 + ' \\_ '

        filename = f'{self.prefix}.{node}'
        pathname = self.pathnames.get(node, '?')
        exit_status = self.exit_statuses.get(node, '?')
        stdout = 'Yes' if node in self.stdout else 'No'
        stderr = 'Yes' if node in self.stderr else 'No'
        argv = self.argvs.get(node, '?')

        if exit_status != 0:
            exit_status = f'\033[91m{exit_status}\033[0m'

        self.data.append((filename, pathname, stdout, stderr, exit_status, f'{padding}{argv}'))

        for child in self.childs[node]:
            self.fill_table(child, level=level + 1)


def main():
    prefix = os.environ.get('PREFIX', 'output')
    root_path = os.environ.get('ROOT_PATH', os.getcwd())

    stp = StraceTreePrinter(prefix=prefix, root_path=root_path)
    stp.run()


if __name__ == '__main__':
    main()
