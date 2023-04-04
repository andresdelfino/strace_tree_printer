# Description

`strace_tree_printer` prints a tree out of a set of logs produced by an `strace` execution that used flags `-f`, `-ff`, and option `-o`.

# Example

After running `strace -f -ff -o output -s 10000 -tt -v man -H man`, `strace_tree_printer` outputs:

```
Log           Pathname          Output    Exit    Argv
------------  ----------------  --------  ------  ------------------------
output.23149  /usr/bin/man          err   3       man -H man
output.23150  # /usr/bin/man    out       0        \_ # man -H man
output.23151  # /usr/bin/man    out       0        \_ # man -H man
output.23157  # /usr/bin/man    out       0            \_ # man -H man
output.23152  # /usr/bin/man    out       0        \_ # man -H man
output.23156  # /usr/bin/man    out       0            \_ # man -H man
output.23153  /usr/bin/preconv  out       ?        \_ preconv -e UTF-8
output.23154  /usr/bin/tbl      out       ?        \_ tbl
output.23155  /usr/bin/groff        err   3        \_ groff -mandoc -Thtml

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

A number sign preceding a pathname and argv means the content mirrors the values of the child's parent, as no `execve(2)` call was found.

# See also

[Marius Gedminas](https://github.com/mgedmin)'s [strace-process-tree](https://github.com/mgedmin/strace-process-tree).