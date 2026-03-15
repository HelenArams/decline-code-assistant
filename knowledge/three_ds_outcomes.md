# 3-D Secure 2 authentication outcomes

3-D Secure 2 (EMV 3DS) authenticates the cardholder with the issuer before
authorization. Its outcome changes both the chance of approval and who carries
chargeback liability. The outcome is reported in `transStatus` and carried into
authorization as the ECI value plus a cryptogram (CAVV on Visa, AAV on
Mastercard).

## transStatus values

- **Y - Authenticated.** Frictionless or after a successful challenge. Full
  liability shift. Submit authorization with ECI 05 (Visa) / 02 (Mastercard) and
  the cryptogram.
- **A - Attempted.** The issuer or the directory server's attempts server
  could not authenticate but proof of attempt was generated. Liability shift
  still applies on most schemes. ECI 06 (Visa) / 01 (Mastercard).
- **N - Not authenticated.** The cardholder failed or abandoned the challenge.
  Do not authorize; the issuer will most likely decline and liability stays with
  the merchant. Offer another payment method.
- **U - Unavailable.** Technical problem at the ACS or directory server. The
  merchant may authorize without authentication (ECI 07 / 00) but carries
  liability, or retry authentication shortly after.
- **R - Rejected.** The issuer refused to authenticate; treat as a decline.
- **C - Challenge required.** Interim status; the cardholder must complete a
  challenge. Only a problem when the challenge is never completed.
- **D - Decoupled authentication required.** Authentication happens out of
  band; poll for the final result.
- **I - Informational only.** Used for exemption-flagged transactions where the
  issuer acknowledged but did not authenticate.

## Frictionless versus challenge

In the frictionless flow the issuer's risk engine approves based on the device
and transaction data (over a hundred data elements) without involving the
cardholder. A challenge adds friction and abandonment. Sending rich,
accurate data (billing address, email, phone, account age, device data)
raises the frictionless rate and reduces `N` outcomes caused by abandonment.

## Exemptions under PSD2 SCA

Within the EEA and UK, merchants may request an exemption so the issuer skips
authentication:

- **Low value** - under 30 EUR, with cumulative caps tracked by the issuer.
- **Transaction risk analysis (TRA)** - acquirer fraud rate below the
  threshold for the amount band.
- **Trusted beneficiary** - cardholder has allow-listed the merchant.
- **Merchant-initiated transactions (MIT)** and recurring payments after the
  first agreement are out of scope, provided the first transaction was
  authenticated and the stored-credential indicators are set correctly.

An exemption request the issuer rejects produces a soft decline (`65` on
Mastercard, `1A` on Visa). The correct response is to authenticate with 3DS2
and resubmit, not to retry without authentication.

## How 3DS status explains declines

- Rows with `three_ds_status = none` on EEA/UK cards and codes `65`/`1A` are SCA
  soft declines; the fix is step-up authentication.
- Rows with `three_ds_status = N` followed by an authorization attempt indicate
  the integration authorizes after a failed challenge; it should not.
- Rows with `three_ds_status = U` clustering in time point to an ACS or
  directory-server outage; retry authentication rather than skipping it.
- A high share of `05` on unauthenticated traffic often drops once 3DS2 is
  used, because issuers approve authenticated transactions more readily.
