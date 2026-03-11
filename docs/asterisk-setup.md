# SIP2SDR — Asterisk PBX Setup

This guide covers the Asterisk (or FreePBX) configuration required to connect SIP2SDR.

## SIP Accounts

Create one SIP account for each extension in your `config.yaml`. SIP2SDR registers as a SIP endpoint and waits for incoming calls — it never places outbound calls.

### Asterisk `pjsip.conf` (or FreePBX PJSIP endpoint)

```ini
; Repeat for sip2sdr-1 through sip2sdr-4

[sip2sdr-1]
type=endpoint
transport=transport-tls
auth=sip2sdr-1-auth
aors=sip2sdr-1-aor
context=sip2sdr
allow=!all,ulaw,alaw        ; PCMU and/or PCMA only
dtmf_mode=rfc4733
media_encryption=sdes
media_encryption_optimistic=no

[sip2sdr-1-auth]
type=auth
auth_type=userpass
username=sip2sdr-1
password=secret1

[sip2sdr-1-aor]
type=aor
max_contacts=1
```

> **Codec note:** `ulaw` = PCMU (G.711 µ-law), `alaw` = PCMA (G.711 A-law).
> If your `config.yaml` sets `codec: pcmu`, list only `ulaw`. For `pcma`, list only `alaw`.

### TLS Transport

```ini
[transport-tls]
type=transport
protocol=tls
bind=0.0.0.0:5061
cert_file=/etc/asterisk/keys/asterisk.pem
priv_key_file=/etc/asterisk/keys/asterisk.key
; Self-signed certificates are accepted by SIP2SDR when verify_certs: false
```

### Dialplan (`extensions.conf`)

Create a context that routes calls to the SIP2SDR extensions:

```ini
[sip2sdr]
; Allow any internal extension to call SIP2SDR channels
exten => sip2sdr-1,1,Dial(PJSIP/sip2sdr-1)
exten => sip2sdr-2,1,Dial(PJSIP/sip2sdr-2)
exten => sip2sdr-3,1,Dial(PJSIP/sip2sdr-3)
exten => sip2sdr-4,1,Dial(PJSIP/sip2sdr-4)

; Or use a feature code, e.g. *80 calls channel 1 (default ch 67):
exten => *80,1,Dial(PJSIP/sip2sdr-1)
```

## SRTP

SIP2SDR requires SRTP (`srtp: required` in config). On the Asterisk side, `media_encryption=sdes` enables SRTP key exchange via SDP. Both sides must agree — if Asterisk is configured with `media_encryption=no`, calls will be rejected.

## Generating a Self-Signed TLS Certificate

```bash
cd /etc/asterisk/keys
openssl req -x509 -nodes -newkey rsa:4096 \
    -keyout asterisk.key -out asterisk.pem \
    -days 3650 -subj "/CN=pbx.example.com"
chmod 600 asterisk.key
asterisk -rx "module reload res_pjsip.so"
```

Set `verify_certs: false` in `config.yaml` to allow SIP2SDR to accept this self-signed certificate.
