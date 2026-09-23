# CLAUDE.md - Project Configuration for SuperABAP

## gstack Configuration

Use the `/browse` skill from gstack for all web browsing. Never use `mcp__claude-in-chrome__*` tools.

### Available gstack Skills

**Planning & Strategy:**
- `/office-hours` — Product interrogation with 6 forcing questions
- `/plan-ceo-review` — Strategic challenge with 4 scope modes
- `/plan-eng-review` — Engineering feasibility review
- `/plan-design-review` — Design review before building
- `/plan-devex-review` — Developer experience review
- `/plan-tune` — Iterative plan refinement
- `/autoplan` — End-to-end feature planning and execution

**Design:**
- `/design-consultation` — Design consultation and ideation
- `/design-shotgun` — Parallel design exploration
- `/design-html` — HTML/CSS design implementation
- `/design-review` — Design review and critique

**Review & Quality:**
- `/review` — Comprehensive code review (bugs, security, performance)
- `/ship` — Release engineering and PR creation
- `/land-and-deploy` — Landing and deployment
- `/canary` — Canary deployment
- `/qa` — Quality assurance with real browser testing
- `/qa-only` — QA without browser
- `/cso` — Security audit (OWASP + STRIDE)
- `/devex-review` — Developer experience review
- `/careful` — Careful, deliberate changes

**Code Generation & Tools:**
- `/codex` — Codex-style code generation
- `/browse` — Web browsing with gstack browser
- `/scrape` — Web scraping
- `/connect-chrome` — Connect to Chrome DevTools
- `/make-pdf` — Generate PDFs
- `/diagram` — Generate diagrams

**Documentation:**
- `/document-generate` — Generate documentation
- `/document-release` — Release documentation

**Workflow & State:**
- `/context-save` — Save context
- `/context-restore` — Restore context
- `/retro` — Engineering retrospective
- `/investigate` — Root cause investigation
- `/freeze` / `/unfreeze` — Freeze/unfreeze files
- `/guard` — Guard against changes
- `/gstack-upgrade` — Upgrade gstack

**Learning & Setup:**
- `/learn` — Learn from codebase
- `/setup-browser-cookies` — Setup browser cookies
- `/setup-deploy` — Setup deployment
- `/setup-gbrain` — Setup gbrain (AI memory)

**Specialized:**
- `/benchmark` — Performance benchmarking
- `/benchmark-models` — Model benchmarking
- `/skillify` — Convert workflows to skills
- `/spec` — Specification generation
- `/sync-gbrain` — Sync gbrain
- `/ios-clean` / `/ios-design-review` / `/ios-fix` / `/ios-qa` / `/ios-sync` — iOS workflows
- `/pair-agent` — Pair programming agent
- `/open-gstack-browser` — Open gstack browser
- `/health` — Health check
- `/landing-report` — Landing page report