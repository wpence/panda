#!/usr/bin/env python3

from sys import argv, exit, path
import capstone
path.append("..")
from panda import Panda, ffi, blocking

# Single arg of arch, defaults to i386
arch = "i386" if len(argv) <= 1 else argv[1]
panda = Panda(generic=arch)
md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_64)
insn_cache = {} # address -> disassembly string
executed_pcs = [] # List of addresses we executed

# Run a command in the guest
@blocking
def my_runcmd():
    panda.revert_sync('root')
    panda.run_serial_cmd("find . /proc/self")
    panda.end_analysis()

def generate_insns(env, tb):
    # Disassemble each basic block and store in insn_cache
    if tb.pc in insn_cache: return

    code_buf = ffi.new("char[]", tb.size)
    code = panda.virtual_memory_read(env, tb.pc, tb.size)

    insn_cache[tb.pc] = ""
    for i in md.disasm(code, tb.pc):
        insn_cache[tb.pc] += ("0x%x:\t%s\t%s\n" %(i.address, i.mnemonic, i.op_str))

@panda.cb_after_block_translate(name="before", procname="find")
def before_block_trans(env, tb):
    # Before we translate each block in find cache its disassembly
    generate_insns(env, tb)
    return 0

@panda.cb_before_block_exec(name="exec", procname="find")
def before_block_exec(env, tb):
    # At each BB's execution in 'find', ensure translation is cached and add to executed_pcs
    pc = panda.current_pc(env)
    if pc not in insn_cache: # If we miss the cache, update it
        generate_insns(env, tb)
    executed_pcs.append(pc)
    return 0

panda.queue_async(my_runcmd)
panda.run()

print("Observed {} distinct basic blocks".format(len(insn_cache)))
#for pc in executed_pcs: print(insn_cache[pc])
