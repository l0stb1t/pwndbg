#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Common types, and routines for manually loading types from file
via GCC.
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import glob
import os
import subprocess
import sys
import tempfile

import gdb

import pwndbg.events
import pwndbg.gcc
import pwndbg.memoize

module = sys.modules[__name__]


def is_pointer(value):
    type = value

    if isinstance(value, gdb.Value):
        type = value.type

    type = type.strip_typedefs()
    return type.code == gdb.TYPE_CODE_PTR


def lookup_types(*types):
    for type_str in types:
        try:
            return gdb.lookup_type(type_str)
        except Exception as e:
            exc = e
    raise exc


@pwndbg.events.start
@pwndbg.events.stop
def update():

    module.char   = gdb.lookup_type('char')
    module.ulong  = lookup_types('unsigned long', 'uint')
    module.long   = lookup_types('long', 'int')
    module.uchar  = lookup_types('unsigned char', 'ubyte')
    module.ushort = lookup_types('unsigned short', 'ushort')
    module.uint   = lookup_types('unsigned int', 'uint')
    module.void   = gdb.lookup_type('void')
    module.uint8  = module.uchar
    module.uint16 = module.ushort
    module.uint32 = module.uint
    module.uint64 = lookup_types('unsigned long long', 'ulong')

    module.int8   = gdb.lookup_type('char')
    module.int16  = gdb.lookup_type('short')
    module.int32  = gdb.lookup_type('int')
    module.int64  = lookup_types('long long', 'long')

    module.ssize_t = module.long
    module.size_t = module.ulong

    module.pvoid  = void.pointer()
    module.ppvoid = pvoid.pointer()
    module.pchar  = char.pointer()

    module.ptrsize = pvoid.sizeof

    if pvoid.sizeof == 4: module.ptrdiff = uint32
    if pvoid.sizeof == 8: module.ptrdiff = uint64

    module.null = gdb.Value(0).cast(void)

# Call it once so we load all of the types
update()

tempdir = tempfile.gettempdir() + '/pwndbg'
if not os.path.exists(tempdir):
    os.mkdir(tempdir)

# Trial and error until things work
blacklist = ['regexp.h', 'xf86drm.h', 'libxl_json.h', 'xf86drmMode.h',
'caca0.h', 'xenguest.h', '_libxl_types_json.h', 'term_entry.h', 'slcurses.h',
'pcreposix.h', 'sudo_plugin.h', 'tic.h', 'sys/elf.h', 'sys/vm86.h',
'xenctrlosdep.h', 'xenctrl.h', 'cursesf.h', 'cursesm.h', 'gdbm.h', 'dbm.h',
'gcrypt-module.h', 'term.h', 'gmpxx.h', 'pcap/namedb.h', 'pcap-namedb.h',
'evr.h', 'mpc.h', 'fdt.h', 'mpfr.h', 'evrpc.h', 'png.h', 'zlib.h', 'pngconf.h',
'libelfsh.h', 'libmjollnir.h', 'hwloc.h', 'ares.h', 'revm.h', 'ares_rules.h',
'libunwind-ptrace.h', 'libui.h', 'librevm-color.h', 'libedfmt.h','revm-objects.h',
'libetrace.h', 'revm-io.h','libasm-mips.h','libstderesi.h','libasm.h','libaspect.h',
'libunwind.h','libmjollnir-objects.h','libunwind-coredump.h','libunwind-dynamic.h']

def load(name):
    """Load symbol by name from headers in standard system include directory"""
    try:
        return gdb.lookup_type(name)
    except gdb.error:
        pass

    # s, _ = gdb.lookup_symbol(name)

    # Try to find an architecture-specific include path
    arch = pwndbg.arch.current.split(':')[0]

    include_dir = glob.glob('/usr/%s*/include' % arch)

    if include_dir:
        include_dir = include_dir[0]
    else:
        include_dir = '/usr/include'

    source = '#include <fstream>\n'

    for subdir in ['', 'sys', 'netinet']:
        dirname = os.path.join(include_dir, subdir)
        for path in glob.glob(os.path.join(dirname, '*.h')):
            if any(b in path for b in blacklist):
              continue
            print(path)
            source += '#include "%s"\n' % path


    source += '''
{name} foo;
'''.format(**locals())

    filename = '%s/%s_%s.cc' % (tempdir, arch, '-'.join(name.split()))

    with open(filename, 'w+') as f:
        f.write(source)
        f.flush()
        os.fsync(f.fileno())

    compile(filename)

    return gdb.lookup_type(name)

def compile(filename=None, address=0):
    """Compile and extract symbols from specified file"""
    if filename is None:
        print("Specify a filename to compile.")
        return

    objectname = os.path.splitext(filename)[0] + ".o"

    if not os.path.exists(objectname):
        gcc     = pwndbg.gcc.which()
        gcc    += ['-w', '-c', '-g', filename, '-o', objectname]
        subprocess.check_output(' '.join(gcc), shell=True)

    add_symbol_file(objectname, address)

def add_symbol_file(filename=None, address=0):
    """Read additional symbol table information from the object file filename"""
    if filename is None:
        print("Specify a symbol file to add.")
        return

    with pwndbg.events.Pause():
        gdb.execute('add-symbol-file %s %s' % (filename, address), from_tty=False, to_string=True)
