import ctypes
import os

def load():
    lib_path = os.environ.get(
        "SCAP_FFI_LIB",
        os.path.join("vendor", "tasklib", "target", "release", "libscap_ffi.so"),
    )
    lib_path = os.path.abspath(lib_path)

    lib = ctypes.CDLL(lib_path)

    # set known signatures
    lib.scap_version.restype = ctypes.c_char_p

    return lib

def version() -> str:
    lib = load()
    return lib.scap_version().decode("utf-8")
