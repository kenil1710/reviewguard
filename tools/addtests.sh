#!/bin/bash
# Append a test block before the unittest main block. Keeping `main` last is not
# cosmetic: unittest.main() runs at import time, so anything defined after it
# never registers and would silently not be a test at all.
set -euo pipefail
F=test/test_logic.py
python3 - "$F" <<'PY'
import io, sys
p = sys.argv[1]
s = io.open(p, encoding="utf8").read()
i = s.find('\nif __name__ == "__main__":')
if i >= 0:
    io.open(p, "w", encoding="utf8").write(s[:i])
PY
cat >> "$F"
cat >> "$F" <<'EOF2'

if __name__ == "__main__":
    unittest.main(verbosity=1, buffer=False)
EOF2
