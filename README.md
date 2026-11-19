# Catchly

**Never lose an enquiry.**

Catchly is an AI-assisted front desk for small businesses. It answers customer questions from the business's own documents, captures leads when it can't answer, and schedules polite follow-ups so no enquiry goes cold.

Built first for coaching centres and educational institutes, but nothing in the code is limited to them.

![Tests](https://github.com/piyush2707/catchly/actions/workflows/tests.yml/badge.svg)

> **Status: V1, pre-pilot.** Core features work and are tested. See [Limitations](#limitations) before using it with real customer data.

---

## What it does

1. **Answers from your documents.** A business adds its fee sheet, schedule, and FAQs. Catchly answers visitors' questions using only that text, and shows where the answer came from.
2. **Says "I don't know" instead of guessing.** If no passage matches well enough, it hands off to a human.
3. **Captures leads.** When it can't answer, the chat widget asks for a name and phone number.
4. **Schedules follow-ups.** Each new lead gets up to 3 reminders (after 24 hours, 3 days, and 7 days). They stop as soon as staff mark the lead as replied, converted, or lost.
5. **Gives staff a panel.** One page to see stats and leads, add documents, and open ready-to-send WhatsApp messages for due follow-ups.

## How it works

```
Visitor ──► Chat widget ──► POST /ask ──► keyword search over the
                                          business's documents
                              │
                    answer found? ── yes ──► reply with source
                              │
                              no
                              ▼
                      Lead form ──► POST /leads ──► 3 follow-ups scheduled
                                                         │
Staff ──► /panel ──► "Get due follow-ups" ──► WhatsApp link, text ready
```

- **Search:** BM25 keyword ranking in pure Python. No external AI service is needed yet.
- **Storage:** SQLite.
- **Backend:** FastAPI.
- **Isolation:** every business has its own ID and API key. One business cannot read another's documents or leads.

## Quick start

**Requires:** Python 3.11+

```bash
git clone https://github.com/piyush2707/catchly.git
cd catchly
pip install -r requirements.txt

# Choose your own long random secret. Never commit it.
CATCHLY_ADMIN_KEY=your-long-random-secret uvicorn app.main:app
```

Then open:

| Page | Purpose |
|---|---|
| `/docs` | Interactive API docs. Create your first business here. |
| `/panel` | Staff panel |
| `/demo?b=BUSINESS_ID` | Try the chat widget |
| `/health` | Health check |

### Create a business

In `/docs`, run **POST /businesses** with your admin secret in the `x-admin-key` field:

```json
{ "name": "Test Centre" }
```

The response contains a `business_id` and an `api_key`. **The key is shown only once.** Store it safely.

## Embed the chat widget

Add one line to any website:

```html
<script
  src="https://YOUR-HOST/widget.js"
  data-business="BUSINESS_ID"
  data-title="How can we help?"
  data-color="#f97316"
  defer></script>
```

`data-title` and `data-color` are optional.

## Configuration

| Variable | Required | Purpose |
|---|---|---|
| `CATCHLY_ADMIN_KEY` | Yes | Secret that allows creating businesses |
| `CATCHLY_DB` | No | Path to the SQLite file (default `catchly.db`). Point it at a persistent disk in production. |
| `PORT` | No | Set by most hosts. The Dockerfile reads it. |

## API overview

| Endpoint | Auth | Description |
|---|---|---|
| `GET /health` | None | Health check |
| `POST /ask` | None (rate-limited) | Ask a question |
| `POST /leads` | None (rate-limited) | Create a lead |
| `POST /businesses` | `X-Admin-Key` | Create a business and its API key |
| `POST /documents` | `X-API-Key` | Add a document |
| `GET /documents` | `X-API-Key` | List documents |
| `GET /leads` | `X-API-Key` | List leads |
| `PATCH /leads/{id}` | `X-API-Key` | Update a lead's status |
| `POST /followups/run` | `X-API-Key` | Get due follow-ups and mark them sent |
| `GET /dashboard` | `X-API-Key` | Lead and follow-up counts |

Public endpoints are limited to 30 requests per minute per visitor. API keys are stored only as hashes.

## Deploy

The repo includes a `Dockerfile`, so it runs on any host that supports Docker. On Render:

1. Create a **Web Service** from this repo with the **Docker** runtime.
2. Set the health check path to `/health`.
3. Add the environment variable `CATCHLY_ADMIN_KEY`.
4. **For real data:** use a paid instance with a persistent disk (for example mounted at `/var/data`) and set `CATCHLY_DB=/var/data/catchly.db`.

Free web services have no persistent disk, so the database is wiped on every restart. Use them only for demos. Check your host's current pricing and limits before choosing a plan.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -v
```

Tests cover chunking, search, follow-up scheduling, API keys, business isolation, rate limiting, and the main API flows. GitHub Actions runs them on every push and pull request.

## Project structure

```
catchly/
├── app/
│   ├── main.py          # FastAPI app and endpoints
│   ├── db.py            # SQLite schema and connection
│   ├── businesses.py    # Business creation and API key checks
│   ├── chunking.py      # Splits documents into passages
│   ├── search.py        # BM25 keyword search
│   ├── followups.py     # Follow-up schedule and messages
│   ├── ratelimit.py     # In-memory rate limiter
│   └── static/
│       ├── widget.js    # Embeddable chat widget
│       ├── dashboard.html
│       └── demo.html
├── tests/
├── .github/workflows/tests.yml
├── Dockerfile
├── requirements.txt
└── requirements-dev.txt
```

## Limitations

Catchly is an early version. Know these before a real pilot:

- **Follow-ups are not sent automatically.** Staff tap a WhatsApp link with the message prefilled. Automatic sending would need the official WhatsApp Business API or an email service.
- **The WhatsApp link assumes India:** 10-digit numbers get the `91` prefix.
- **Search matches keywords, not meaning.** A question using different words than the document may not match, and then it hands off to a human.
- **Answers are passages from your documents**, not rewritten text.
- **Language:** built and tested for English. Hindi and Hinglish need dedicated work.
- **No login accounts, key recovery, or multi-staff roles yet.** A lost API key means creating a new business.
- **Rate limiting is basic.** It is in memory, per server, and resets on restart.
- **No automatic backups.** A persistent disk is not a backup.
- **Personal data.** Catchly stores names and phone numbers. Before using it with real customers, add a privacy notice and check the data protection rules that apply to you.

## Roadmap

- [ ] Home page and screenshots
- [ ] Database backups
- [ ] Meaning-based search and Hindi/Hinglish support
- [ ] LLM-phrased answers, still restricted to the business's documents
- [ ] Automatic WhatsApp or email follow-ups
- [ ] Staff accounts and API key reset
- [ ] First real-world pilot

## Contributing

Issues and pull requests are welcome. Please keep changes small and tested.

## License

Add a license file before sharing the code publicly. MIT is a common choice.

---

Built by [Piyush](https://www.linkedin.com/in/piyush2707).
