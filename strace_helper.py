import collections
import glob
import os
import re


class StraceTreePrinter:
    def __init__(self, *, prefix):
        self.childs = collections.defaultdict(list)
        self.pathnames = {}
        self.argvs = {}
        self.exit_statuses = {}
        self.prefix = prefix

    def run(self):
        child_pids = set()
        pids = set()

        root_path = os.environ.get('ROOT_PATH', os.getcwd())

        for file in glob.glob(os.path.join(root_path, f'{self.prefix}.*')):
            pid = int(file.split('.')[-1])
            pids.add(pid)

            with open(file) as f:
                for line in f:
                    command_match = re.search(r'execve\(([^]]+\])', line)
                    if command_match:
                        pathname, argv = command_match[1].split(', ', maxsplit=1)
                        self.pathnames[pid] = pathname[1:-1]
                        self.argvs[pid] = argv[2:-2].replace('", "', ' ')

                    exit_status_match = re.search(r'exit_group\((\d+)\)', line)
                    if exit_status_match:
                        self.exit_statuses[pid] = int(exit_status_match[1])

                    child_pid_match = re.search(r'(clone|__clone2|clone3)\(.+?(\d+)$', line)
                    if child_pid_match:
                        child_pid = int(child_pid_match[2])
                        self.childs[pid].append(child_pid)
                        child_pids.add(child_pid)

        root_pid = (pids - child_pids).pop()

        self.print_tree(root_pid)

    def print_tree(self, node, level=0):
        SEPARATOR = '---'

        padding = ' ' * level * 4

        filename = f'{self.prefix}.{node}'
        pathname = self.pathnames.get(node, '(none)')
        argv = self.argvs.get(node, '(none)')
        exit_status = self.exit_statuses.get(node, '(none)')

        if exit_status != 0:
            print('\033[91m', end='')

        print(f'{padding}{filename}:', pathname, SEPARATOR, argv, SEPARATOR, exit_status)

        print('\033[0m', end='')

        for child in self.childs[node]:
            self.print_tree(child, level=level + 1)


def main():
    stp = StraceTreePrinter(prefix='output')
    stp.run()


if __name__ == '__main__':
    main()
