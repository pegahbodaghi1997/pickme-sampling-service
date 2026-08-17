import hashlib
import sys

if len(sys.argv) != 2:
    raise SystemExit("Usage: python scripts/hash_password.py <password>")
print(hashlib.sha256(sys.argv[1].encode()).hexdigest())
