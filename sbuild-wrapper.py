#!/usr/bin/python3

import os
import sys
import subprocess

# A wrapper for sbuild that replaces _ with " " because bash just cant...

def call(*args, env=os.environ):
    return subprocess.check_call(list(args), env=env)


args = sys.argv
args.pop(0)

finalargs=[]
finalargs.append("sbuild")

for arg in args:
  arg = arg.replace("_", " ")
  finalargs.append(arg)

print(finalargs)
call(*finalargs)

