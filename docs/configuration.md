# SIP2SDR — Configuration Reference

SIP2SDR is configured via a single YAML file. Copy `config.example.yaml` and edit it.

```bash
cp config.example.yaml config.yaml
```

## Top-Level Fields

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `mode` | string | `marine`, `test` | Channel plan to use. `marine` = ITU VHF (156–162 MHz). `test` = LPD433 (433–434 MHz). |

## `sdr` Section

SDR hardware parameters.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `device` | string | `hackrf` | osmosdr device type |
| `sample_rate` | int | `8000000` | ADC sample rate (Hz). Use 8 Msps for marine, 2 Msps for LPD. |
| `gain_lna` | int | `32` | LNA gain (dB) |
| `gain_vga` | int | `30` | VGA gain (dB) |
| `gain_amp` | bool | `false` | Enable RF preamplifier |

## `sip` Section

SIP PBX connection and extension credentials.

| Field | Type | Description |
|-------|------|-------------|
| `registrar` | string | SIP registrar URI, e.g. `sip:pbx.example.com` |
| `transport` | string | `tls` (SIP over TLS on port 5061) |
| `srtp` | string | `required` — all media must be encrypted |
| `verify_certs` | bool | `false` to accept self-signed TLS certificates |
| `extensions` | list | List of SIP extension objects (see below) |

### Extension Object

| Field | Type | Description |
|-------|------|-------------|
| `username` | string | SIP username (account name in Asterisk) |
| `password` | string | SIP password |
| `default_channel` | int | Channel to tune when a call connects |

Up to 4 extensions are supported (one per demodulator chain).

## `audio` Section

Audio pipeline settings.

| Field | Type | Values | Default | Description |
|-------|------|--------|---------|-------------|
| `codec` | string | `pcmu`, `pcma` | `pcmu` | G.711 codec. `pcmu` = µ-law (RTP PT 0). `pcma` = A-law (RTP PT 8). Use `pcma` if your PBX requires it. |
| `sample_rate` | int | `8000` | `8000` | Audio sample rate in Hz. Must be 8000. |
| `buffer_size` | int | — | `4000` | Ring buffer size in samples (~0.5 s at 8 kHz). |

## Example Configuration

```yaml
mode: marine

sdr:
  device: "hackrf"
  sample_rate: 8000000
  gain_lna: 32
  gain_vga: 30
  gain_amp: false

sip:
  registrar: "sip:pbx.example.com"
  transport: tls
  srtp: required
  verify_certs: false
  extensions:
    - username: "sip2sdr-1"
      password: "secret1"
      default_channel: 67
    - username: "sip2sdr-2"
      password: "secret2"
      default_channel: 16

audio:
  codec: pcmu
  sample_rate: 8000
  buffer_size: 4000
```
