# Description

`strace_tree_printer` prints a tree out of a set of logs produced by an `strace` execution that used flags `-f`, `-ff`, and option `-o`.

# Example

After running `strace -f -ff -o output -s 10000 -tt -v man -H man`, `strace_tree_printer` outputs:

```
Log           Call    First entry      Last entry       PPID    Pathname          Output    Exit    Argv
------------  ------  ---------------  ---------------  ------  ----------------  --------  ------  ------------------------
output.28124  execve  21:31:58.884560  21:31:58.928956  ?       /usr/bin/man          err   3       man -H man
output.28125  clone   21:31:58.912443  21:31:58.915788  28124   /usr/bin/man !    out       0           man -H man !
output.28126  clone   21:31:58.915801  21:31:58.925521  28124   /usr/bin/man !    out       0           man -H man !
output.28131  clone   21:31:58.920371  21:31:58.924343  28126   /usr/bin/man !    out       0               man -H man !
output.28127  clone   21:31:58.916126  21:31:58.927320  28124   /usr/bin/man !    out       0           man -H man !
output.28132  clone   21:31:58.920347  21:31:58.926392  28127   /usr/bin/man !    out       0               man -H man !
output.28128  clone   21:31:58.916359  21:31:58.928313  28124   /usr/bin/preconv  out       ?           preconv -e UTF-8
output.28129  clone   21:31:58.916646  21:31:58.928125  28124   /usr/bin/tbl      out       ?           tbl
output.28130  clone   21:31:58.916915  21:31:58.927467  28124   /usr/bin/groff        err   3           groff -mandoc -Thtml

```

# Installation

On a virtual environment, run:

```
pip install git+https://github.com/andresdelfino/strace_tree_printer.git
```

# Use

```
usage: strace_tree_printer [-h] [--prefix PREFIX] [--root-path ROOT_PATH]

options:
  -h, --help            show this help message and exit
  --prefix PREFIX
  --root-path ROOT_PATH
```

PREFIX is the argument passed to the `-o` option of the `strace` execution. Defaults to "output".

ROOT_PATH is the path where the logs are located. Defaults to the working directory.

# Output

The Output column tells if the command wrote to `stdout` or `stderr`.

An exit status of "?" means the thread was terminated by another thread of the same thread group (see `exit_group(2)`).

An exclamation mark following a pathname or argv means the preceding value mirrors the values of the child's parent, as no `execve(2)` call was found.

# See also

[Marius Gedminas](https://github.com/mgedmin)'s [strace-process-tree](https://github.com/mgedmin/strace-process-tree).