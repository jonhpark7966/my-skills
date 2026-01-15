# Upload metadata and translation

Requirements:
- Use YouTube Data API v3 with OAuth.
- Privacy status: unlisted.
- Title and description translated to Korean with Codex CLI.
- OAuth client secret path is TODO (leave as a placeholder).

Translation prompt skeleton:

Title: <ORIGINAL_TITLE>
Description: <ORIGINAL_DESCRIPTION>

Rules:
- Translate to Korean.
- Keep proper nouns consistent.
- Do not add marketing or extra content.

Codex invocation:

`codex exec --skip-git-repo-check "@file PROMPT"`

Upload payload essentials:
- snippet.title (Korean)
- snippet.description (Korean)
- status.privacyStatus = "unlisted"

If implementing a script, use google-auth-oauthlib + googleapiclient.
