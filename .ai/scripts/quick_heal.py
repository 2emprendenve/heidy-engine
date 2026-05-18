# .ai/scripts/quick_heal.py
import subprocess
import sys
import os
import hashlib
import json
import time

SRC_DIR = "src"
SNAPSHOT_FILE = os.path.join("..", "state_snapshot.json")
TIMEOUT = 5

def load_snapshot():
    if os.path.exists(SNAPSHOT_FILE):
        with open(SNAPSHOT_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_snapshot(files_hashes):
    with open(SNAPSHOT_FILE, 'w') as f:
        json.dump(files_hashes, f, indent=2)

def md5(fname):
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def compile_file(py_file):
    try:
        subprocess.run([sys.executable, "-m", "py_compile", py_file],
                       check=True, capture_output=True, timeout=TIMEOUT)
        return True, ""
    except subprocess.CalledProcessError as e:
        return False, e.stderr.decode()
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)

def run_sanity_checks(py_file):
    try:
        result = subprocess.run([sys.executable, py_file],
                               capture_output=True, timeout=TIMEOUT)
        if result.returncode != 0:
            return False, result.stderr.decode()
        return True, ""
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)

def main():
    if not os.path.exists(SRC_DIR):
        print(f"No se encontró carpeta '{SRC_DIR}'. Buscando .py en raíz.")
        py_files = [f for f in os.listdir('.') if f.endswith('.py') and f != os.path.basename(__file__)]
    else:
        py_files = []
        for root, dirs, files in os.walk(SRC_DIR):
            for f in files:
                if f.endswith('.py'):
                    py_files.append(os.path.join(root, f))

    if not py_files:
        print("No se encontraron archivos .py para verificar.")
        return

    snapshot = load_snapshot()
    results = {"OK": 0, "FAIL": 0, "TIMEOUT": 0}
    current_hashes = {}

    for py_file in py_files:
        print(f"Verificando {py_file}...")
        current_hashes[py_file] = md5(py_file)

        ok, err = compile_file(py_file)
        if not ok:
            print(f"  [FAIL] Compilación: {err.strip()}")
            results["FAIL"] += 1
            continue

        ok, err = run_sanity_checks(py_file)
        if err == "Timeout":
            print(f"  [TIMEOUT]")
            results["TIMEOUT"] += 1
        elif not ok:
            print(f"  [FAIL] Ejecución: {err.strip()}")
            results["FAIL"] += 1
        else:
            print(f"  [OK]")
            results["OK"] += 1

    save_snapshot(current_hashes)

    print(f"\nResumen: [OK: {results['OK']}, FAIL: {results['FAIL']}, TIMEOUT: {results['TIMEOUT']}]")
    if results["FAIL"] > 0:
        print("Se detectaron fallos. Consulta state_snapshot.json para restaurar últimos hashes funcionales.")

if __name__ == "__main__":
    main()
