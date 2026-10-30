# Blockplan

A simple, drag-and-drop way to map how an organisation works, with an AI helper you can ask in plain English. It is built for people new to architecture work: no framework names, no acronyms, and nothing to learn before you start.

## What it does

- **Six plain rows.** Why we do it (goals), What we do (activities), Who does it (teams), What we need to know (information), Systems we use, and What it runs on (technology).
- **Drag and drop.** Drag a block onto the map, or tap it to add one. Drag from the round dot on a block to another block to connect them. The connecting words are filled in for you.
- **Today and future.** Mark anything as in place today, planned, or being removed, then switch between Today and Future to see the map before and after.
- **Health.** Mark each block as working well, needing attention, or causing problems.
- **Costs.** Add a yearly running cost and a one-off cost to any block. The Costs tab totals them, compares today with the future, and works out how long the changes take to pay for themselves.
- **Stakeholders.** Choose Stakeholders at the top to see the people and groups who have a say in the changes or are affected by them, on a simple grid: more say towards the top, more affected towards the right. Note how each one feels, what they care about, and how you will keep them on side, and link them to the blocks they care about. Blocks show how many stakeholders care about them.
- **Checks.** Simple rules flag gaps as you build, such as a system nothing uses, an activity no one does, or a plan that depends on something being removed.
- **AI helper.** Build a starter map, explain the map, find what is missing, spot risks, overlaps, and savings, and suggest stakeholders. It always shows its suggested changes first, and you choose whether to put them on the map.
- **Bring in what you already have.** Import a spreadsheet (CSV), such as an application list from a CMDB. Blockplan matches the columns for you and shows a preview first.
- **Share it.** Download a PDF report, a picture of the map or the stakeholder grid for slides, a spreadsheet, or an ArchiMate model for Archi and other architecture tools.
- **Shared maps.** Maps are saved on the Blockplan server, so everyone using it sees the same maps. If two people save the same map at once, the second person is told and can load the other version or keep theirs as a copy.

## Quick start

You need Python 3.10 or newer.

**macOS or Linux**

```bash
unzip blockplan.zip && cd blockplan
./run.sh
```

**Windows**

Unzip `blockplan.zip`, open the `blockplan` folder, and double-click `run.bat`.

Then open http://localhost:8080. The first run creates an example map so you can see how it works.

To switch on the AI helper, open the `.env` file the first run created, add your Claude API key after `ANTHROPIC_API_KEY=`, and restart Blockplan.

## The AI helper

Blockplan can use Claude, a model running on your own machine through [Ollama](https://ollama.com), or both. Set `AI_MODE` in `.env`:

| AI_MODE | What happens |
|---|---|
| `auto` | Claude first. If Claude is not set up or does not answer, the local model is used. This is the default. |
| `claude` | Claude only. |
| `local` | The local model only. Nothing about your maps leaves this machine. |
| `off` | No AI helper. Everything else still works. |

**Claude.** Get an API key at https://platform.claude.com/settings/keys and put it in `ANTHROPIC_API_KEY`. Create the key for a single workspace; if it works across several, also set `ANTHROPIC_WORKSPACE_ID`. `CLAUDE_MODEL` defaults to `claude-sonnet-5-5`. `claude-haiku-5-5` is quicker and cheaper; `claude-opus-5-5` is the most capable for large maps.

**Local model.** Install Ollama, then run `ollama pull qwen2.5:7b`. Larger models such as `qwen2.5:14b` give better answers if the machine has the memory. Set `OLLAMA_MODEL` to match.

When the helper is used, the map's names, descriptions, owners, statuses, and costs are sent to the model with the question. Use `AI_MODE=local` if that information must stay on your network.

## Running it for a team

**Linux server, starting on boot**

```bash
cd blockplan
bash deploy/setup.sh
```

This installs Blockplan as a service. Edit `.env`, then `systemctl --user restart blockplan`.

**Docker**

```bash
cd blockplan
cp .env.example .env      # then add your API key
docker compose up -d
```

Maps are kept in `./data`. If Ollama runs on the host, the container reaches it automatically.

**Sign-in.** Set `AUTH_USER` and `AUTH_PASSWORD` in `.env` to ask everyone for a username and password. This is a simple shared login. If Blockplan is reachable from outside your network, put it behind HTTPS, for example with a reverse proxy, a VPN, or Tailscale.

## Your maps

- Everything is in one file, `data/blockplan.db`.
- `bash scripts/backup.sh` makes a dated copy in `backups/`, and is safe to run while Blockplan is running.
- **Maps → Download this map as a file** gives a `.blockplan.json` file. **Maps → Open a map file** brings one back in, on this or another Blockplan.

## Importing and exporting

Everything is in the **Maps** menu.

**Import from a spreadsheet.** Save the spreadsheet as CSV, with one row per item and column names in the first row. Blockplan recognises common names, for example:

| Blockplan field | Column names it recognises |
|---|---|
| Name | Name, Application, System, Title, Service |
| Kind of block | Type, Kind, Category, Layer. Values such as Application, Capability, Team, Data, Infrastructure, or Goal pick the row. |
| Description | Description, Notes, Purpose, Summary |
| Who looks after it | Any column with "owner" in its name, Responsible, Accountable |
| Status | Status, Lifecycle, Stage, Phase. Planned, Proposed, or Pipeline means planned. Retire, Sunset, Decommission, or To be replaced means being removed. |
| Health | Health, RAG, Condition, Technical fit. Green, Amber, and Red work, as do Good, Fair, and Poor. |
| Yearly cost | Any column with "cost", "annual", or "opex" in its name. 40k and £1.2m both work. |
| One-off cost | One-off, Setup, Capex, Project cost, Implementation |

You can change any match before importing. Rows without a kind go into the row you choose, Systems by default. Importing into an existing map updates blocks with the same name instead of adding them twice. **Download as a spreadsheet** gives a file in the same layout, so it doubles as a template.

**PDF report.** A landscape A4 report: a summary with counts, costs, payback, and stakeholders, then the map (split across pages if it's wide), the stakeholder grid and details, costs, the checks, and a list of everything on the map.

**Picture.** A PNG of whatever you're looking at, either the map (respecting Everything, Today, or Future) or the stakeholder grid. It always uses the light colours, so it suits slides.

**ArchiMate.** A model in the Open Group exchange format (ArchiMate 3.1). In Archi, use **File → Import → Open Exchange XML Model**. Blockplan's rows become ArchiMate elements:

| Blockplan | ArchiMate |
|---|---|
| Goal | Goal |
| Activity | Business Function |
| Team | Business Actor |
| Information | Business Object |
| System | Application Component |
| Technology | Node |
| Stakeholder | Stakeholder |

Connections become the matching ArchiMate relationship. For example, a team "does" an activity becomes Assignment, a system "supports" an activity becomes Serving, and a system "runs on" technology becomes Serving from the technology to the system. Where ArchiMate wouldn't allow the matching type, the connection becomes an Association, so every relationship is valid. Owner, status, health, and costs come across as properties. The model includes three views: the map, the stakeholder grid, and what stakeholders care about.

The PDF maker (jsPDF and jsPDF-AutoTable, both MIT licensed) is included in `app/static/vendor/`, so exports work without internet access.

## Settings

All settings live in `.env`. See `.env.example` for the full list with notes. The main ones:

| Setting | Default | Notes |
|---|---|---|
| `PORT` | `8080` | Web address port |
| `HOST` | `0.0.0.0` | Use `127.0.0.1` to allow this computer only |
| `DATA_DIR` | `./data` | Where maps are stored |
| `AUTH_USER`, `AUTH_PASSWORD` | empty | Set both to require sign-in |
| `AI_MODE` | `auto` | `auto`, `claude`, `local`, or `off` |
| `ANTHROPIC_API_KEY` | empty | Needed for Claude |
| `CLAUDE_MODEL` | `claude-sonnet-5-5` | Any Claude model name |
| `OLLAMA_URL`, `OLLAMA_MODEL` | `http://localhost:11434`, `qwen2.5:7b` | Local model |

## Project layout

```
app/main.py          web server: the page, saving maps, the AI helper route, sign-in
app/storage.py       maps in SQLite, with a check that stops people overwriting each other
app/llm.py           Claude first, local model fallback
app/prompts.py       what the helper is told, kept in one place
app/config.py        reads .env
app/static/          the page itself, its fonts, and the PDF maker (no internet needed)
deploy/              Linux service setup
scripts/backup.sh    copies all maps to backups/
run.sh, run.bat      start it on macOS, Linux, or Windows
Dockerfile, docker-compose.yml
```

## Fonts

Bricolage Grotesque, Hanken Grotesk, and JetBrains Mono are included under the SIL Open Font Licence. The licence files are in `app/static/fonts/`.

## Licence

MIT. See `LICENSE`.
