# Tutorials

See the README quickstart for opening RAW files and P190 navigation.

```python
from segd import SegdFile

sf = SegdFile(
    ["shot1.RAW", "shot2.RAW"],
    navigation="line.P190",
)
trace = sf.trace[0]
```
