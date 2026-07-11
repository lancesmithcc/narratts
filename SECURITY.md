# Security policy

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting for this repository. Do not open a public issue
containing secrets, exploit details, private voice samples, or personal data.

## Deployment guidance

NarraTTS is local-first. It is not hardened as a multi-tenant public API.

- Keep the default loopback bind unless remote access is required.
- Configure a long random `TTS_API_KEYS` value before LAN or internet access.
- Use HTTPS through a reverse proxy for remote access.
- Treat uploaded voices as sensitive biometric/personal data.
- Do not share `.env`, Hugging Face tokens, TLS private keys, or the runtime data directory.
- Review generated speech and obtain permission before cloning another person's voice.

Supported security fixes target the latest release on the default branch.
