# icalatomic

Atomic file writes for Python

```python
import json

from icalatomic import atomic_write

with atomic_write("path/to/summary.json", "w") as file:
    json.dump({"foo": 12}, file)

with atomic_write("path/to/data.bin", "wb") as file:
    file.write(b"\x00\xff")
```

`atomic_write()` には標準の `open()` と同じ引数を渡すことができます。

ただし第2引数 `mode` は必須で、ファイル作成系のモード (`"w"`, `"x"` 系) のみ指定可です。

---

Personal library; no support provided.