"""Install the verified, self-hosted browser runtime while building Pages."""
import hashlib
import io
import shutil
import tarfile
from urllib.request import urlopen

VERSION="0.27.7"
EXPECTED="9bc8f127db6c590b191b9aee754022cb41b1a36c7bac233776c11c5ecb541be8"
FILES={"pyodide.js","pyodide.asm.js","pyodide.asm.wasm","python_stdlib.zip","pyodide-lock.json"}
LICENSES={
    "LICENSE-pyodide":("pyodide/pyodide/0.27.7/LICENSE","1f256ecad192880510e84ad60474eab7589218784b9a50bc7ceee34c2b91f1d5"),
    "LICENSE-cpython":("python/cpython/v3.12.7/LICENSE","3b2f81fe21d181c499c59a256c8e1968455d6689d269aa85373bfb6af41da3bf"),
    "LICENSE-emscripten":("emscripten-core/emscripten/3.1.58/LICENSE","620a78084fc7ca97c0b5dea9abf891f3ffcadfdbf305276f099c9c4e12fc1d86"),
}

def checked_download(location, url, expected, limit):
    blob=location.read_bytes() if location.exists() else None
    if blob is None or hashlib.sha256(blob).hexdigest()!=expected:
        with urlopen(url,timeout=60) as response:
            blob=response.read(limit+1)
        if len(blob)>limit or hashlib.sha256(blob).hexdigest()!=expected:
            raise ValueError("SHA-256 do componente do runtime não conferiu")
        location.parent.mkdir(parents=True,exist_ok=True)
        location.write_bytes(blob)
    return blob

def install(output, cache, root):
    name=f"pyodide-core-{VERSION}.tar.bz2"
    blob=checked_download(cache/name,f"https://github.com/pyodide/pyodide/releases/download/{VERSION}/{name}",
                          EXPECTED,25_000_000)
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
    for name,(src,digest) in LICENSES.items():
        (output/(name+".txt")).write_bytes(
            checked_download(cache/(VERSION+"-"+name),"https://raw.githubusercontent.com/"+src,digest,128_000))
    (output/"THIRD-PARTY.txt").write_text(
        "Unmodified Pyodide runtime and corresponding source:\n"
        "https://github.com/pyodide/pyodide/tree/0.27.7\n"
        "https://github.com/python/cpython/tree/v3.12.7\n"
        "https://github.com/emscripten-core/emscripten/tree/3.1.58\n",encoding="utf-8")
    for name in ("__init__.py","domain.py","capture.py"):
        shutil.copy2(root/"pipeline"/name,output/name)
