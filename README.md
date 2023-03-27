# Description

`strace_tree_printer` prints a tree out of a set of logs produced by an `strace` execution that used flags `-f`, `-ff`, and option `-o`.

# Example

After running `strace -f -ff -o output -s 10000 -t -v man -H man`, `strace_tree_printer` outputs:

```
Log           Pathname          Output    Exit    Argv
------------  ----------------  --------  ------  ------------------------
output.17885  /usr/bin/man          err   3       man -H man
output.17886  ?                 out       0        \_ ?
output.17887  ?                 out       0        \_ ?
output.17893  ?                 out       0            \_ ?
output.17888  ?                 out       0        \_ ?
output.17892  ?                 out       0            \_ ?
output.17889  /usr/bin/preconv  out       ?        \_ preconv -e UTF-8
output.17890  /usr/bin/tbl      out       ?        \_ tbl
output.17891  /usr/bin/groff        err   3        \_ groff -mandoc -Thtml
```

# Installation

On a virtual environment, run:

```
pip install git+ssh://git@github.com/andresdelfino/strace_tree_printer.git
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

The Output column tells if the command wrote on `stdout` or `stderr`.

The Exit column content is red if the exit status is non-zero.

The Pathname and Argv columns content is "?" if no `execve(2)` call was found.
