# Squelch Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `analog.standard_squelch_ff` to each NFM demodulator chain so callers hear silence when no carrier is present.

**Architecture:** Insert a GNU Radio `standard_squelch_ff` block between the NFM demodulator and the rational resampler in `DemodChain`. The block outputs zeros when signal power is below threshold. A `squelch_threshold_db` field is added to `SdrConfig` and wired through `SdrFlowgraph` to each chain.

**Tech Stack:** Python 3.10+, GNU Radio (`gnuradio.analog.standard_squelch_ff`), pytest

---

### Task 1: Add `squelch_threshold_db` to `SdrConfig` and config loader

**Files:**
- Modify: `src/sip2sdr/config.py`
- Modify: `tests/conftest.py`
- Modify: `tests/test_config.py`

**Step 1: Write the failing test**

Add to `tests/test_config.py` inside `TestLoadConfig`:

```python
def test_sdr_squelch_threshold_default(self, tmp_path: Path, marine_config_dict: dict) -> None:
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml.dump(marine_config_dict))
    cfg = load_config(cfg_file)
    assert cfg.sdr.squelch_threshold_db == pytest.approx(-20.0)

def test_sdr_squelch_threshold_custom(self, tmp_path: Path, marine_config_dict: dict) -> None:
    marine_config_dict["sdr"]["squelch_threshold_db"] = -30.0
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(yaml.dump(marine_config_dict))
    cfg = load_config(cfg_file)
    assert cfg.sdr.squelch_threshold_db == pytest.approx(-30.0)
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_config.py::TestLoadConfig::test_sdr_squelch_threshold_default tests/test_config.py::TestLoadConfig::test_sdr_squelch_threshold_custom -v
```

Expected: FAIL with `AttributeError: 'SdrConfig' object has no attribute 'squelch_threshold_db'`

**Step 3: Add `squelch_threshold_db` to `SdrConfig` dataclass**

In `src/sip2sdr/config.py`, update `SdrConfig`:

```python
@dataclass(frozen=True)
class SdrConfig:
    """SDR hardware and capture parameters."""

    device: str
    sample_rate: int
    gain_lna: int
    gain_vga: int
    gain_amp: bool
    squelch_threshold_db: float = -20.0
```

Then update the loader in `load_config` where `SdrConfig` is constructed:

```python
sdr = SdrConfig(
    device=sdr_raw["device"],
    sample_rate=int(sdr_raw["sample_rate"]),
    gain_lna=int(sdr_raw["gain_lna"]),
    gain_vga=int(sdr_raw["gain_vga"]),
    gain_amp=bool(sdr_raw["gain_amp"]),
    squelch_threshold_db=float(sdr_raw.get("squelch_threshold_db", -20.0)),
)
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_config.py -v
```

Expected: all PASS

**Step 5: Commit**

```bash
git add src/sip2sdr/config.py tests/test_config.py
git commit -m "feat: add squelch_threshold_db to SdrConfig"
```

---

### Task 2: Add squelch block to `DemodChain`

**Files:**
- Modify: `src/sip2sdr/sdr/demod_chain.py`
- Modify: `tests/test_demod_chain.py`

**Step 1: Write the failing tests**

Add to `tests/test_demod_chain.py` inside `TestDemodChain`:

```python
def test_squelch_block_present(self) -> None:
    from gnuradio import analog
    buf = RingBuffer(capacity=4000)
    chain = DemodChain(
        center_freq_offset=0.0,
        sdr_sample_rate=8_000_000,
        channel_bandwidth=12_500,
        buf=buf,
        squelch_threshold_db=-20.0,
    )
    assert chain.squelch_block is not None
    assert isinstance(chain.squelch_block, analog.standard_squelch_ff)

def test_squelch_default_threshold(self) -> None:
    buf = RingBuffer(capacity=4000)
    chain = DemodChain(
        center_freq_offset=0.0,
        sdr_sample_rate=8_000_000,
        channel_bandwidth=12_500,
        buf=buf,
    )
    # Default threshold should be -20 dB
    assert chain.squelch_block.threshold() == pytest.approx(-20.0)

def test_set_squelch_threshold(self) -> None:
    buf = RingBuffer(capacity=4000)
    chain = DemodChain(
        center_freq_offset=0.0,
        sdr_sample_rate=8_000_000,
        channel_bandwidth=12_500,
        buf=buf,
    )
    chain.set_squelch_threshold(-35.0)
    assert chain.squelch_block.threshold() == pytest.approx(-35.0)
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_demod_chain.py -v
```

Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'squelch_threshold_db'`

**Step 3: Update `DemodChain`**

In `src/sip2sdr/sdr/demod_chain.py`:

1. Add `squelch_threshold_db: float = -20.0` parameter to `__init__`:

```python
def __init__(
    self,
    center_freq_offset: float,
    sdr_sample_rate: int,
    channel_bandwidth: int,
    buf: RingBuffer,
    squelch_threshold_db: float = -20.0,
) -> None:
```

2. After `self._nfm = analog.fm_demod_cf(...)`, add:

```python
self._squelch = analog.standard_squelch_ff(squelch_threshold_db, False)
```

The second argument (`False`) means hysteresis is disabled; the block uses a simple threshold comparison.

3. Add `squelch_block` property:

```python
@property
def squelch_block(self) -> analog.standard_squelch_ff:
    """The squelch block (for flowgraph connection and threshold adjustment)."""
    return self._squelch
```

4. Add `set_squelch_threshold` method:

```python
def set_squelch_threshold(self, threshold_db: float) -> None:
    """Update the squelch threshold without stopping the flowgraph.

    Args:
        threshold_db: New threshold in dB. More negative = more sensitive.
    """
    self._squelch.set_threshold(threshold_db)
    logger.debug("Squelch threshold set to %.1f dB", threshold_db)
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_demod_chain.py -v
```

Expected: all PASS

**Step 5: Commit**

```bash
git add src/sip2sdr/sdr/demod_chain.py tests/test_demod_chain.py
git commit -m "feat: add standard_squelch_ff to DemodChain"
```

---

### Task 3: Wire squelch block into the flowgraph connection

The squelch block is instantiated in Task 2, but not yet connected in the flowgraph. The connection is made in `SdrFlowgraph`, which calls `self.connect(...)`.

**Files:**
- Modify: `src/sip2sdr/sdr/flowgraph.py`
- Modify: `tests/test_flowgraph.py`

**Step 1: Write the failing test**

Open `tests/test_flowgraph.py` and check if there are existing construction tests. Add:

```python
def test_chains_have_squelch_block(self) -> None:
    """Each chain's squelch block is not None after flowgraph construction."""
    # (test only runs if gnuradio and osmosdr are available)
    osmosdr = pytest.importorskip("osmosdr")  # noqa: F841
    from sip2sdr.audio.ring_buffer import RingBuffer
    from sip2sdr.channels import ChannelMode
    from sip2sdr.sdr.flowgraph import SdrFlowgraph

    buffers = [RingBuffer(4000) for _ in range(4)]
    fg = SdrFlowgraph(
        mode=ChannelMode.TEST,
        sdr_device_args="hackrf=0",
        sample_rate=2_000_000,
        gain_lna=32,
        gain_vga=30,
        gain_amp=False,
        initial_channels=[1, 2, 3, 4],
        buffers=buffers,
        squelch_threshold_db=-20.0,
    )
    for chain in fg.chains:
        assert chain.squelch_block is not None
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_flowgraph.py::test_chains_have_squelch_block -v
```

Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'squelch_threshold_db'`

**Step 3: Update `SdrFlowgraph`**

In `src/sip2sdr/sdr/flowgraph.py`:

1. Add `squelch_threshold_db: float = -20.0` to `SdrFlowgraph.__init__` signature (after `buffers`):

```python
def __init__(
    self,
    mode: ChannelMode,
    sdr_device_args: str,
    sample_rate: int,
    gain_lna: int,
    gain_vga: int,
    gain_amp: bool,
    initial_channels: list[int],
    buffers: list[RingBuffer],
    squelch_threshold_db: float = -20.0,
) -> None:
```

2. Pass it to `DemodChain`:

```python
chain = DemodChain(
    center_freq_offset=offset,
    sdr_sample_rate=sample_rate,
    channel_bandwidth=_CHANNEL_BW,
    buf=buf,
    squelch_threshold_db=squelch_threshold_db,
)
```

3. Update the `self.connect(...)` calls for each chain to insert squelch between nfm and resamp:

```python
self.connect(self._src, chain.xlat_block)
self.connect(chain.xlat_block, chain.nfm_block)
self.connect(chain.nfm_block, chain.squelch_block)
self.connect(chain.squelch_block, chain.resamp_block)
self.connect(chain.resamp_block, chain.sink_block)
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_flowgraph.py -v
```

Expected: all PASS (tests that require hardware will skip)

**Step 5: Commit**

```bash
git add src/sip2sdr/sdr/flowgraph.py tests/test_flowgraph.py
git commit -m "feat: wire squelch block into SdrFlowgraph connection chain"
```

---

### Task 4: Pass squelch threshold from config in `__main__.py`

**Files:**
- Modify: `src/sip2sdr/__main__.py`

No new tests needed — this is pure wiring of already-tested components.

**Step 1: Update the `SdrFlowgraph` constructor call**

In `src/sip2sdr/__main__.py`, update the `SdrFlowgraph(...)` call:

```python
fg = SdrFlowgraph(
    mode=cfg.mode,
    sdr_device_args=f"{cfg.sdr.device}=0",
    sample_rate=cfg.sdr.sample_rate,
    gain_lna=cfg.sdr.gain_lna,
    gain_vga=cfg.sdr.gain_vga,
    gain_amp=cfg.sdr.gain_amp,
    initial_channels=[e.default_channel for e in cfg.sip.extensions],
    buffers=buffers,
    squelch_threshold_db=cfg.sdr.squelch_threshold_db,
)
```

**Step 2: Run full test suite**

```bash
pytest -v
```

Expected: all PASS (GNU Radio tests skip on dev machine)

**Step 3: Commit**

```bash
git add src/sip2sdr/__main__.py
git commit -m "feat: wire squelch threshold from config to SdrFlowgraph"
```

---

### Task 5: Update `config.example.yaml` and docstring

**Files:**
- Modify: `config.example.yaml`
- Modify: `src/sip2sdr/sdr/demod_chain.py` (docstring only)

**Step 1: Add squelch field to `config.example.yaml`**

In `config.example.yaml`, add `squelch_threshold_db` to the `sdr` section:

```yaml
sdr:
  device: "hackrf"
  sample_rate: 8000000  # 8 Msps for marine, 2 Msps for test
  gain_lna: 32
  gain_vga: 30
  gain_amp: false
  squelch_threshold_db: -20  # dB; -40 sensitive, -20 moderate, -10 aggressive
```

**Step 2: Update `DemodChain` class docstring**

In `src/sip2sdr/sdr/demod_chain.py`, update the `DemodChain` Args section:

```
squelch_threshold_db: Squelch threshold in dB (default -20.0).
    More negative opens squelch on weaker signals. Uses FM noise
    signature detection (analog.standard_squelch_ff).
```

**Step 3: Commit**

```bash
git add config.example.yaml src/sip2sdr/sdr/demod_chain.py
git commit -m "docs: add squelch_threshold_db to config example and DemodChain docstring"
```
