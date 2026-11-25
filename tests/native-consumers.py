import ctypes
import json
from pathlib import Path
import subprocess
import sys

catalog = json.loads(Path(sys.argv[1]).read_text())
library = catalog["libraries"]["Native"]
for program in [
    """import ctypes
p=ctypes.CDLL(LIBRARY)
p.projection_initialize.restype=ctypes.c_int
assert p.projection_initialize()==1
p.projection_answer.argtypes=[ctypes.c_uint32]
p.projection_answer.restype=ctypes.c_uint32
for i in [*range(100),0xffffffff]: assert p.projection_answer(i)==(i+EXPECTED) % (1<<32)
print('ctypes Lean allocation and exported UInt32 ABI PASS')
""",
    """from cffi import FFI
f=FFI(); f.cdef('int projection_initialize(void); uint32_t projection_answer(uint32_t);')
p=f.dlopen(LIBRARY)
assert p.projection_initialize()==1
for i in [*range(100),0xffffffff]: assert p.projection_answer(i)==(i+EXPECTED) % (1<<32)
print('CFFI Lean allocation and exported UInt32 ABI PASS')
""",
]:
    subprocess.run([sys.executable,"-c","LIBRARY="+repr(library)+"\nEXPECTED="+str(int(sys.argv[2]))+"\n"+program],check=True)
