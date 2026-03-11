# Squelch Design

**Date:** 2026-03-11
**Status:** Approved

## Summary

Add automatic squelch to each NFM demodulator chain using GNU Radio's `analog.standard_squelch_ff` block. When no carrier is present, the squelch outputs silence (zeros) so callers hear nothing instead of demodulator noise.

## Architecture

Insert `analog.standard_squelch_ff` between the NFM demodulator and the resampler in each `DemodChain`:

```
freq_xlat → nfm → squelch → resamp → ring_buffer_sink
```

### How It Works

The standard FM squelch measures signal power after the FM discriminator:
- **No carrier** → discriminator outputs broadband noise → high noise power → squelch closes → outputs zeros
- **Carrier present** → discriminator outputs voice audio → lower noise power → squelch opens → audio passes through

When squelched, the block outputs `0.0` samples. `_RingBufferSink` writes these as silence (int16 zeros) to the ring buffer, so callers hear silence rather than noise.

## Configuration

New field in the `sdr` section of `config.yaml`:

```yaml
sdr:
  squelch_threshold_db: -20  # dB; range -40 (sensitive) to -10 (aggressive)
```

Default: `-20 dB`. Typical tuning:
- `-40 dB`: opens on very weak signals (may let noise through)
- `-20 dB`: good starting point for LPD433 / Marine VHF
- `-10 dB`: only opens on strong signals

## Code Changes

### `src/sip2sdr/sdr/demod_chain.py`
- Add `squelch_threshold_db: float = -20.0` parameter to `DemodChain.__init__`
- Instantiate `analog.standard_squelch_ff(threshold, False)` after `_nfm`
- Connect `_nfm → _squelch → _resamp` (was `_nfm → _resamp`)
- Add `squelch_block` property
- Add `set_squelch_threshold(db: float)` method

### `src/sip2sdr/sdr/flowgraph.py`
- Accept `squelch_threshold_db` in `SdrFlowgraph.__init__`
- Pass it to each `DemodChain`

### `src/sip2sdr/config.py`
- Add `squelch_threshold_db: float = -20.0` to the SDR config dataclass

### `src/sip2sdr/__main__.py`
- Pass `squelch_threshold_db` from config to `SdrFlowgraph`

## Testing

- Unit tests for `DemodChain` with squelch configured (mock GNU Radio blocks)
- Verify `set_squelch_threshold` calls through to the underlying block
- Verify `flowgraph.py` passes threshold from config to chains
