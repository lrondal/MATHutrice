# MATHutrice

An LLM-based tutor that helps EPF first-year students practise mathematical
tools. A student signs in, picks a **notion** (trigonometry, logarithms,
polynomials…), and works through **competences** with generated exercises —
multiple choice, open answer, and step by step. Answers are corrected by the
**LLM endpoint**, scores are stored per competence, and the tutor recommends
the notions a student is weakest on. A free chat is available alongside the
exercises. Teachers and admins get their own pages, including PDF upload.

The vocabulary this project uses — *notion*, *competence*, **connexion de
développement**, **LLM endpoint** — is defined in [`GLOSSARY.md`](GLOSSARY.md).
Decisions that shaped the code are in [`docs/adr/`](docs/adr/).

## Run it locally

Requires **Python 3.14** (the exact version is in `.python-version`) and
[uv](https://docs.astral.sh/uv/), which installs that Python and the locked
dependency versions from `uv.lock`.

```sh
uv sync
. .venv/bin/activate
cp .env.example .env
```

Then set `LLM_API_KEY` in `.env` to the key for your LLM endpoint. Everything
else in `.env.example` has a working default for a local run. Start the
application from the repository root:

```sh
uvicorn mathutrice.app:app --port 8000
```

It listens on <http://localhost:8000/>.

On the first start the tables are created and the reference data is inserted:
the notions and competences of `referentiel.py`, and one demonstration account
per role:

| Email | Role |
| --- | --- |
| `eleve@epf.fr` | Student |
| `enseignant@epf.fr` | Teacher |
| `admin@epf.fr` | Admin |

Only rows that are missing get inserted, so nothing is written when the data is
already there and restarting is safe. Only `@epf.fr` and `@epfedu.fr` addresses
may sign in.

To check that a fresh clone actually works, follow
[`docs/smoke-test.md`](docs/smoke-test.md).

## Configuration

Every variable the application reads is listed, with comments, in
`.env.example`. In short:

| Variable | Meaning |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy URL. SQLite by default; PostgreSQL where it is deployed. |
| `LLM_BASE_URL` | The OpenAI-compatible **LLM endpoint** every LLM call goes through. **Required.** |
| `LLM_MODEL` | The model served by that endpoint. **Required.** |
| `LLM_API_KEY` | The key for that endpoint. **Required.** |
| `SESSION_SECRET` | Signing key for the session cookie. **Required.** |
| `AUTH_MODE` | `entra` (the default, Microsoft Entra ID) or `dev`. |
| `DEV_LOGIN_KEY` | Optional shared key protecting the `/dev/login` page. Ignored when `AUTH_MODE=entra`. |
| `CLIENT_ID`, `CLIENT_SECRET`, `TENANT_ID` | The Entra application. Needed when `AUTH_MODE=entra`. |
| `REDIRECT_URL` | Where Entra sends the user back after sign-in — this host's `/auth`. |
| `POST_LOGOUT_REDIRECT_URL` | Where Entra sends the user after sign-out — this host's `/test_login`. |

The LLM defaults in `.env.example` use the Mistral API: get a key at
<https://console.mistral.ai> (a free account works). Any other OpenAI-compatible
endpoint works by changing the three `LLM_*` variables.

No key belongs in the repository. `.env` is not committed; `.env.example` holds
names and placeholders only.

## Connexion de développement (`AUTH_MODE=dev`)

With `AUTH_MODE=dev`, the application serves `/dev/login`, where you pick an
email address and a role and are signed in as that user **with no proof of
identity**. It is what lets you run MATHutrice without Entra credentials. A red
banner shows on every application page while it is on.

**It must never reach production.** In the deployment checklist:

- `AUTH_MODE` unset or `entra`
- `SESSION_SECRET` set to a random value, not the placeholder
- `DATABASE_URL` pointing at the deployed database
- `LLM_API_KEY` supplied by the environment, never committed
- `CLIENT_ID`, `CLIENT_SECRET`, `TENANT_ID`, `REDIRECT_URL` and
  `POST_LOGOUT_REDIRECT_URL` set for the real host

`DEV_LOGIN_KEY` narrows who can reach the `/dev/login` page: when it is set, the
page asks for it and refuses the sign-in without it.

**`SESSION_SECRET` is the real gate, not `DEV_LOGIN_KEY`.** The session cookie
is signed with `SESSION_SECRET`; anyone who knows its value can forge a cookie
for any user and any role, and never sees the sign-in page at all. Leaving the
placeholder from `.env.example` in place on a reachable host makes
`DEV_LOGIN_KEY` decorative.

Signing in from a script means keeping the session cookie between requests:

```sh
curl -s -c cookies.txt -X POST \
  -d 'email=eleve@epf.fr&role=student' \
  http://localhost:8000/dev/login

curl -s -b cookies.txt http://localhost:8000/
```

The first call answers `303` with a `Set-Cookie: session=…`. `role` is
`student`, `teacher` or `admin`; `name` is optional and defaults to the existing
user's name, or one derived from the address. Add `-d 'key=…'` when
`DEV_LOGIN_KEY` is set.

## Deploying on Azure App Service

`.github/workflows/architecture.yml` deploys this fork to **staging**, then
promotes it to **production**: two App Service apps on one B1 Linux plan in
Switzerland North, always on. They hold generated data and no real users, so
each signs in through the
[connexion de développement](#connexion-de-développement-auth_modedev),
guarded by its own `DEV_LOGIN_KEY` and its own `SESSION_SECRET`.

- **On green only.** A push to `course-2026-fallback-clean-branch` whose
  `architecture` and `test` jobs both pass is built into one image, tagged with
  its commit and pushed to GHCR (`ghcr.io/lrondal/mathutrice:<commit>`), then
  deployed to staging. A pull request, or a red run, deploys nothing.
- **The image** (`Dockerfile`) runs one process, `uvicorn mathutrice.app:app`,
  as in [Run it locally](#run-it-locally); the hourly conversation cleanup runs
  inside it. It holds its commit as `REVISION`, which the application sends
  back in the `X-Revision` header of every response. The deploy passes only
  once `/dev/login` answers `200` with that commit, so a previous container
  still answering does not count.
- **Production by Promotion only.** Production is deployed by a run started by
  hand: *Actions → the workflow → Run workflow*, or
  `gh workflow run architecture.yml --repo lrondal/MATHutrice`. It reads the
  workflow's push runs on `course-2026-fallback-clean-branch`, newest first,
  logs each one whose `deploy to staging` did not pass as skipped, and deploys
  the image of the first one that did. It builds nothing: production only runs
  an image staging already ran.

The settings live in each GitHub Environment, `staging` and `production`, never
in a committed file: the variables `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`,
`AZURE_SUBSCRIPTION_ID`, `AZURE_RESOURCE_GROUP` and `AZURE_WEBAPP_NAME`, and
the secrets `DEV_LOGIN_KEY`, `SESSION_SECRET` and `LLM_API_KEY`. Every deploy
writes them to the app's settings (`.github/actions/deploy-to-app-service`),
with `AUTH_MODE=dev`, the SQLite `DATABASE_URL` and Mistral's `LLM_BASE_URL`
and `LLM_MODEL`. The workflow logs in to Azure through OpenID Connect, as its
GitHub Environment, and stores no Azure password. The GHCR package must be
public: App Service pulls it without credentials.

**Known limit: the data is reset at every deploy and every restart.** The
SQLite file lives on the container's own disk, not on App Service's `/home`, a
network share on which SQLite cannot take its locks. Each start creates the
tables and seeds them again, so everything written since the last start is
lost, uploaded PDFs included.

## Layout

```
mathutrice/            the application package
  app.py               FastAPI routes
  models.py            the SQLModel tables
  database.py          the engine and session
  referentiel.py       the notions and competences reference data
  seed.py              inserts the missing reference data at startup
  llm_client.py        the OpenAI-compatible client every LLM call goes through
  fonctions_python/    exercise generation and correction
  lacune_evaluation/   gap detection from a student's answers
  templates/, static/  the pages
  rag_documents/       PDFs uploaded by teachers (runtime data, kept out of the wheel)
docs/                  the smoke test and the ADRs
scripts/               the architecture checks
Dockerfile             the image every environment runs
.github/               the check, and the deploy to staging
```

Package boundaries are machine-checked: a name starting with `_` cannot be
imported from outside its package, and packages may not form an import cycle.
Read [`mathutrice/README.md`](mathutrice/README.md) before adding a package or
importing across one, and run the checks with:

```sh
tach check
python scripts/check_cycles.py
```

## Licence

MIT — see [`LICENSE`](LICENSE).
