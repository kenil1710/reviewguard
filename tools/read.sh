#!/bin/bash
# `genlayer call` prints a banner and then the value. Pull just the JSON.
genlayer call "$1" "${2:-read}" ${3:+--args "$3"} 2>/dev/null | python3 -c "
import sys
t = sys.stdin.read()
i = t.find('Result:')
print(t[i+7:].strip() if i >= 0 else t.strip())
"
