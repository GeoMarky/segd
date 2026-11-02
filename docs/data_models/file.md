# File model

`SegdFile` opens one demultiplexed SEG-D RAW record or an ordered list of records.

Each RAW file is one shot gather (one FFID). A `RecordCatalog` maps the flat global
trace index `0 … num_traces-1` onto `(record, local_channel)`.

Logical binary headers are synthesized from general headers so MDIO-style consumers
can call `binary_header.to_dict()` without parsing SEG-D GH blocks themselves.
