"""Install the verified, self-hosted browser runtime while building Pages."""
import hashlib
import io
import shutil
import tarfile
from urllib.request import urlopen

VERSION="0.27.7"
EXPECTED="9bc8f127db6c590b191b9aee754022cb41b1a36c7bac233776c11c5ecb541be8"
FILES={"pyodide.js","pyodide.asm.js","pyodide.asm.wasm","python_stdlib.zip","pyodide-lock.json"}

def install(output, cache, root):
    location=cache/f"pyodide-core-{VERSION}.tar.bz2"
    blob=location.read_bytes() if location.exists() else None
    if blob is None or hashlib.sha256(blob).hexdigest()!=EXPECTED:
        url=f"https://github.com/pyodide/pyodide/releases/download/{VERSION}/pyodide-core-{VERSION}.tar.bz2"
        with urlopen(url,timeout=60) as response:
            blob=response.read(25_000_001)
        if hashlib.sha256(blob).hexdigest()!=EXPECTED:
            raise ValueError("SHA-256 do runtime não conferiu")
        cache.mkdir(parents=True,exist_ok=True)
        location.write_bytes(blob)
    output.mkdir(parents=True,exist_ok=True)
    done=set()
    with tarfile.open(fileobj=io.BytesIO(blob),mode="r:bz2") as archive:
        for m in archive:
            name=m.name.split("/")[-1]
            if m.isfile() and (name in FILES or name.lower().startswith("license")):
                (output/name).write_bytes(archive.extractfile(m).read())
                done.add(name)
    if not FILES<=done:
        raise ValueError("runtime incompleto")
    for name in ("__init__.py","domain.py","capture.py"):
        shutil.copy2(root/"pipeline"/name,output/name)
