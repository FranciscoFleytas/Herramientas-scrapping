# Instagram Automation Lead Generation & Outreach

## Project Overview
This codebase automates Instagram lead generation and outreach through multi-account scraping and AI-powered messaging. It consists of interconnected Python scripts for scraping followers, managing accounts, and sending personalized DMs via Notion integration.

## Key Components

### 1. Follower Scraping (`scrapping_followers_pryxr.py`)
- **Purpose**: Extract followers from target Instagram profiles using Instaloader
- **Multi-account rotation**: Cycles through multiple IG accounts to avoid rate limits
- **Smart cooldown system**: Temporarily freezes accounts on 429/401 errors, permanent removal on auth failures
- **Filtering**: Applies follower count (2K-100K), post count (>100), and history deduplication
- **Output**: CSV files in `RESULTADOS/` with user data and status

### 2. Outreach Bot (`bot_outreach_escritorio.py`)
- **Purpose**: Send personalized DMs to scraped leads
- **AI messaging**: Uses Gemini 2.5 Flash to generate BBI-style (Business-to-Business Inbound) messages
- **Real name extraction**: Parses Instagram meta tags for authentic display names vs usernames
- **Notion integration**: Fetches leads with "Escribir" status, updates to "Contactado" after sending
- **Anti-detection**: Undetected ChromeDriver with human typing simulation and random delays

### 3. Alternative Selenium Scraper (`proxy_selenium.py`)
- **Purpose**: Browser-based follower scraping with engagement analysis
- **Niche classification**: Maps bios to business categories (Real Estate, Health, Marketing, etc.)
- **Engagement metrics**: Calculates like ratios and filters high-engagement profiles
- **Proxy rotation**: Bright Data residential proxies with session-based auth

## Critical Workflows

### Account Management
- **Session files**: Store as `{username}.session` in project root using Instaloader's `save_session_to_file()`
- **cuentas.json**: Contains `[{"user": "", "pass": "", "sessionid": ""}]` for Selenium login
- **cuentas.txt**: Format `username:password:backup_code` for Instaloader scripts
- **Run `crear_db.py`**: Converts `.session` files to `cuentas.json` by extracting sessionid cookies

### Proxy Configuration
- **Bright Data format**: `brd-customer-{id}-zone-residential_proxy1-country-{country}-session-{random_id}`
- **Authentication**: HTTP proxy with username/password
- **Session rotation**: Generate new session IDs per account/login attempt

### Data Flow
1. Scrape followers → CSV in `RESULTADOS/`
2. Import CSVs to Notion database with "Escribir" status
3. Bot fetches pending leads → Extracts real names → Generates AI messages → Sends DMs → Updates Notion

### Error Handling Patterns
- **Rate limits (429)**: Freeze account for `COOLDOWN_MINUTES` (default 60)
- **Auth failures (401)**: Permanent account removal from pool
- **Network issues**: Retry with different proxy countries/sessions
- **Instagram challenges**: Use backup 2FA codes from `cuentas.txt`

## Project-Specific Conventions

### File Structure
- `RESULTADOS/`: All output CSVs with timestamp naming (`leads_export_YYYY-MM-DD_HH-MM.csv`)
- `SCREENSHOTS_MOBILE/`: Mobile emulation captures (organized by target profile)
- `proxy_auth_*/`: Chrome extension folders for proxy authentication
- `history_*.txt`: Deduplication files tracking processed usernames

### Dependencies & Environment
- **Python packages**: `instaloader`, `undetected-chromedriver`, `selenium`, `google-generativeai`, `requests`
- **External services**: Bright Data proxies, Notion API, Gemini AI
- **Docker stack**: Postgres for data persistence, Redis for caching (defined in `docker-compose.yml`)

### Code Patterns
- **Threading for I/O**: `CSVWriterThread` class for non-blocking CSV writes with `queue.Queue`
- **Human simulation**: `human_type()` function with randomized delays (0.03-0.08s per char)
- **XPath strategies**: Multiple fallback selectors for Instagram UI elements (buttons, inputs)
- **Meta tag parsing**: Extract real names/bios from `og:title` and `og:description` properties

### Build & Run Commands
- **No build required**: Pure Python scripts
- **Typical execution**: `python scrapping_followers_pryxr.py` (requires `cuentas.txt` and Bright Data credentials)
- **Debug mode**: Individual scripts like `debug_botones.py` for UI testing
- **Environment setup**: Ensure Chrome version matches `version_main=142` in UC options

### Integration Points
- **Notion API**: Query database for leads, update status after outreach
- **Gemini prompts**: Structured for BBI messaging with specific formatting rules (no emojis, first names only, two-part messages separated by `|`)
- **CSV import**: Semicolon-delimited with UTF-8 BOM for Excel compatibility

## Common Pitfalls
- **Session expiration**: Regenerate sessions if login fails (delete `.session` files and re-run with credentials)
- **Proxy blocking**: Rotate countries in `PROXY_COUNTRIES` list when residential IPs get flagged
- **UI changes**: Instagram updates break XPaths - test with debug scripts before production runs
- **Rate limiting**: Monitor account pool health; add more accounts when pool shrinks below threshold</content>
<parameter name="filePath">/home/fran/Escritorio/Herramientas-scrapping/scraping_followers/.github/copilot-instructions.md