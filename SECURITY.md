# Security Policy

## Scope

Jarvis Lab publishes only reviewed, reusable components. Local identity files,
conversation memory, credentials, browser data, screenshots, financial data,
and machine-specific configuration are excluded.

## Agent boundaries

- External actions require explicit authorization appropriate to their risk.
- Financial, account-security, payment, and credential operations are never implied by general autonomy.
- Browser and desktop actions should use observe → plan → approve → act → verify.
- Unknown or stale UI state must stop execution rather than trigger blind retries.
- Local model output is untrusted until validated.

## Reporting

Please open a GitHub issue for non-sensitive security design concerns. Do not
post secrets or personal data in public issues.
