from scrap_hypatia.scap_ffi import version

def test_scap_ffi_version():
    assert version() == "1.0.0"
