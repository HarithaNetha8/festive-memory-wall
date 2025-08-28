
---

## 6) `REPORT.md` (structured for Swecha submission)
Save as `REPORT.md`. Fill in screenshots, metrics, and team contributions before submission.

```markdown
# Festival Memory Wall — REPORT.md

## 1. Team Information
- Team name:
- Members (roles & contributions):
  - Member A — Frontend/Streamlit & UI
  - Member B — Backend & DB
  - Member C — AI & language detection
  - Member D — Growth & outreach
  - Member E — Documentation & testing

## 2. Project Overview (MVP)
**Problem:** Rapid loss of regional festival traditions and language-specific descriptions; lack of open datasets.
**Solution:** Festival Memory Wall — a simple offline-first app to collect image + text memories in users’ native languages.

## 3. MVP Scope
- Upload image + description + festival + region + year.
- Language detection (langdetect) & optional festival auto-classify.
- Local SQLite storage and admin CSV export.
- Optional: push to Swecha Corpus API using Bearer Token.

## 4. AI Integration
- Language detection: `langdetect` (offline, lightweight).
- Festival classification: rule-based demo (keywords).
- Future: fine-tune a text classifier using Hugging Face, add translation models.

## 5. Technical Architecture
- Frontend: Streamlit single-page app (`app.py`)
- Storage: SQLite local DB `data/festival_wall.db` (submissions table)
- Images: stored in `assets/images/` (relative paths in DB)
- Corpus: Optionally pushed to Swecha Corpus API (token-based auth)

### DB Schema
