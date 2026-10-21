# Privacy Policy

_Last updated: 2026-10-21_

Broadletter is a personal, open-source tool that runs entirely on your own computer. It
turns the newsletters in your Gmail account into a single news broadcast. There is no
Broadletter server, account or company that receives your data.

## What data it accesses

With your permission (Google OAuth scope `gmail.modify`), Broadletter:

- reads the messages you have labeled `Newsletter`;
- inserts the generated broadcast into your own inbox (`messages.insert`, which sends
  nothing);
- adds the labels `Broadletter/Digested` and `Broadletter/Expired`;
- moves processed or expired newsletters to the trash, where they can be recovered for
  30 days.

Broadletter never sends email, never deletes messages permanently and never follows links
found in emails.

## Where your data goes

Nowhere. Emails are processed on your computer by open-weight models running locally
through Ollama. No email content is sent to any third-party service, AI provider or
analytics service. The OAuth token, the generated broadcasts and an audit log of trashed
messages are stored only in local files on your computer (`secrets/` and `data/`).

## Data sharing

Broadletter does not share, sell or transfer your data to anyone.

Broadletter's use of information received from Google APIs adheres to the
[Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy),
including the Limited Use requirements.

## Revoking access

You can revoke Broadletter's access at any time at
<https://myaccount.google.com/permissions> and delete the local `secrets/` and `data/`
folders.

## Contact

Questions: open an issue in the Broadletter GitHub repository.
