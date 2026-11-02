# Trace model

Physical demux layout for format `8058`:

- File header (general headers, channel sets, extended/external blocks)
- Per channel: demux trace header + IEEE float32 samples (big-endian)

Logical trace headers use SEG-Y-compatible field names. Geometry from an optional
P190 is joined by shot point onto those fields when `navigation=` is set.
