import collections
import glob
import re


def print_tree(childs, commands, node, level=0):
    padding = ' ' * level * 2
    print(f'{padding}{node}:', commands[node])
    for child in childs[node]:
        print_tree(childs, commands, child, level=level + 1)


def main():
    childs = collections.defaultdict(list)
    commands = {}

    child_pids = set()
    pids = set()

    for file in glob.glob('output.*'):
        pid = int(file.split('.')[-1])
        pids.add(pid)

        with open(file) as f:
            for line in f:
                if re.search(r'execve\(', line):
                    commands[pid] = re.search(r'\[[^\]]+\]', line)[0][2:-2].replace('", "', ' ')

                if re.search(r'(clone|__clone2|clone3)\(', line):
                    child_pid = int(line.rsplit('=', maxsplit=1)[1])
                    childs[pid].append(child_pid)
                    child_pids.add(child_pid)

    original_pid = list(pids - child_pids)[0]

    print_tree(childs, commands, original_pid)


if __name__ == '__main__':
    main()
