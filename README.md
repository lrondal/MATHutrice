# MATHutrice

MATHutrice is an LLM-based tutor that helps EPF first-year students practise mathematical tools. Students pick a module (for example *Trigonométrie*), see their progression per competence, and train on generated exercises (multiple-choice, open questions, step-by-step). A chat lets them ask the tutor free questions. Teachers upload course PDFs.

Vocabulary (**connexion de développement**, **impersonation**, **LLM endpoint**…) is defined in [`CONTEXT.md`](CONTEXT.md). Design decisions are in [`docs/adr/`](docs/adr/).

## Run it locally

You need [uv](https://docs.astral.sh/uv/) and an API key for an OpenAI-compatible LLM endpoint. The default endpoint is Mistral: a free account at <https://console.mistral.ai> gives you a key. No Microsoft Entra credentials are needed locally.

```sh
git clone -b course-2026 https://github.com/EPF-MDE/MATHutrice.git
cd MATHutrice
uv sync
cp .env.example .env
```

`uv sync` installs the Python version pinned in `.python-version` (3.14) and the dependency versions in `uv.lock`. If it reports `No interpreter found for Python 3.14.7`, run `uv self update` and retry. Without uv, `pip install -e .` in a virtual environment running Python 3.14 also works, from `pyproject.toml` rather than the lockfile.

Edit `.env` and set `LLM_API_KEY`. Leave the rest as it is, then start the app from the repository root:

```sh
uv run uvicorn mathutrice.app:app --port 8000
```

Open <http://localhost:8000/>. The app creates its tables on startup in the local SQLite file `mathutrice.db`.

A fresh database has no notions yet, so the home page lists no module (see [#20](https://github.com/EPF-MDE/MATHutrice/issues/20)). The chat and the teacher page work as they are.

To check that your clone really runs, follow [`docs/smoke-test.md`](docs/smoke-test.md).

## Configuration

The app reads its settings from the environment, and loads a `.env` file from the directory it starts in. [`.env.example`](.env.example) lists every variable with its comments.

| Variable | Required | Meaning |
| --- | --- | --- |
| `SESSION_SECRET` | always | Signing key of the session cookie. |
| `DATABASE_URL` | always | SQLAlchemy URL. SQLite locally (`sqlite:///./mathutrice.db`), PostgreSQL when deployed. |
| `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` | always | The **LLM endpoint**. Startup fails with `ValueError` naming any that is missing. |
| `AUTH_MODE` | no | `entra` (default) or `dev`. Case and surrounding spaces are ignored; any other value stops startup. |
| `DEV_LOGIN_KEY` | no | Shared key protecting the dev sign-in. Only read when `AUTH_MODE=dev`. |
| `CLIENT_ID`, `CLIENT_SECRET`, `TENANT_ID` | `AUTH_MODE=entra` | Your Microsoft Entra ID app registration. |
| `REDIRECT_URL` | `AUTH_MODE=entra` | Where Entra sends the user back after sign-in: your URL plus `/auth`. Register it in the Entra app. |
| `POST_LOGOUT_REDIRECT_URL` | `AUTH_MODE=entra` | Where Entra sends the user after `/logout`. |

A missing required variable stops startup with `ValueError: <NAME> missing`.

## Signing in with the connexion de développement

Microsoft Entra ID cannot sign anyone in on a clone that is not registered as a redirect URI. So `.env.example` sets `AUTH_MODE=dev`: the app then starts without any Entra variable, and signs anyone in **with no proof of identity**.

- Until you are signed in, any page sends you to `/dev/login`. That page lists the users already in the database by role, each with a one-click button, and a form to sign in as any email, with a name (optional) and a role.
- The email must end in `@epf.fr` or `@epfedu.fr`. An address the database has never seen creates a new user.
- The role you pick (Student, Teacher or Admin) is saved on the user. Without one, an existing user keeps their stored role and a new user becomes a Student. Teachers and Admins land on `/teacher`, Students on `/`.
- A red banner shows on every page with the current email and role. Its *Changer d'utilisateur* link goes back to `/dev/login`: signing in again replaces the session.
- `/logout` clears the session and returns to `/`.
- The session cookie is not restricted to HTTPS in this mode, so it works over `http://localhost`.

Impersonation (an Admin viewing the app as another user through `/impersonate/<email>`) is a different feature and works in both modes.

### `DEV_LOGIN_KEY`

Set `DEV_LOGIN_KEY` on a deployed fork so random visitors cannot sign in as an Admin. Every sign-in must then provide the key: the sign-in page shows a key field, used by the one-click buttons as well. When it is unset, sign-in is open to everyone and the banner says so.

> **`SESSION_SECRET` caveat.** `DEV_LOGIN_KEY` is not real security. The session lives in a cookie signed with `SESSION_SECRET`. While `SESSION_SECRET` is a placeholder, such as the value in `.env.example`, anyone who knows it can forge a session cookie for any user and any role, and skip `DEV_LOGIN_KEY`. On any URL others can reach, replace it with a random secret (for example `python -c "import secrets; print(secrets.token_urlsafe(48))"`).

### Scripted sign-in

`POST /dev/login` takes the form fields `email`, and optionally `name`, `role` (case-insensitive) and `key`. Use `curl -c` to store the session cookie and `-b` to send it back:

```sh
curl -c cookies.txt -i -X POST http://localhost:8000/dev/login \
  -d 'email=bob.leponge@epfedu.fr' -d 'name=Bob Leponge' -d 'role=teacher' \
  -d 'key=<DEV_LOGIN_KEY, only if it is set>'

curl -b cookies.txt http://localhost:8000/conversations
```

A successful sign-in answers `303` with the cookie. Failures:

| Status | Cause |
| --- | --- |
| `401` | `DEV_LOGIN_KEY` is set and `key` is missing or wrong |
| `403` | email outside `@epf.fr` and `@epfedu.fr` |
| `400` | `role` is not Student, Teacher or Admin |

### Turning it off

With `AUTH_MODE` unset or `entra`, none of this exists: `/dev/login` is not registered, there is no banner, the session cookie is HTTPS-only, and sign-in goes through Entra. A `DEV_LOGIN_KEY` left in the environment is ignored, with a `WARNING:` line at startup. Conversely, `AUTH_MODE=dev` prints a `WARNING:` line at startup saying whether a key is set.

## Deployment checklist

Before pointing a deployed environment at real users:

- [ ] `AUTH_MODE` non défini ou `entra`.
- [ ] `CLIENT_ID`, `CLIENT_SECRET`, `TENANT_ID` set, and `REDIRECT_URL` (your URL plus `/auth`) registered as a redirect URI in the Entra app; `POST_LOGOUT_REDIRECT_URL` set.
- [ ] `SESSION_SECRET` is a random secret, not the placeholder. The site is served over HTTPS, since the session cookie is HTTPS-only outside dev mode.
- [ ] `DATABASE_URL` points at PostgreSQL, not the local SQLite file.
- [ ] `LLM_BASE_URL`, `LLM_MODEL` and `LLM_API_KEY` are set for the LLM endpoint you mean to use. On Mistral's free plan, requests may be used for training: turn that off in the admin panel under Privacy before sending real data.

A fork deployed without Entra can run with `AUTH_MODE=dev` and a `DEV_LOGIN_KEY` instead. That is not a deployment for real users.

## Contributing

- Issues live in [GitHub Issues](https://github.com/EPF-MDE/MATHutrice/issues), and the default branch is `course-2026` ([ADR 0001](docs/adr/0001-course-2026-default-branch.md)).
- Package boundaries are machine-checked. Read [`mathutrice/README.md`](mathutrice/README.md) before adding a package or importing across one, then run:

  ```sh
  uv run tach check
  uv run python scripts/check_cycles.py
  ```
