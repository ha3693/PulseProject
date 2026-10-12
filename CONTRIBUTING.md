# Team Collaboration & Contributing Guidelines

Welcome to the **Pulse** team repository! To ensure smooth collaboration and avoid merge conflicts, please review and adhere to the following workflow.

---

## 1. Branching Strategy

We follow a simplified Git feature-branch workflow:
- `main`: Production-ready, stable releases. Protected branch; no direct pushes.
- `develop`: Primary integration branch for upcoming milestones.
- Feature branches: Created off `develop` using the following naming convention:
  - `feat/<short-description>`: New features (e.g. `feat/market-lens-chart`, `feat/reddit-ingestion`)
  - `fix/<short-description>`: Bug fixes (e.g. `fix/yfinance-timezone`)
  - `docs/<short-description>`: Documentation changes (e.g. `docs/api-specs`)

### Daily Workflow
```bash
# 1. Always pull latest develop before branching
git checkout develop
git pull origin develop

# 2. Create your feature branch
git checkout -b feat/your-feature-name

# 3. Work, stage, and commit with meaningful messages
git add .
git commit -m "feat(pipeline): implement GDELT doc search parser"

# 4. Push to remote and open a Pull Request (PR) against develop
git push -u origin feat/your-feature-name
```

---

## 2. Commit Message Convention
Please use conventional commit prefixes:
- `feat:` A new feature
- `fix:` A bug fix
- `docs:` Documentation only changes
- `refactor:` Code change that neither fixes a bug nor adds a feature
- `chore:` Maintenance tasks, dependency updates, configuration

---

## 3. Pull Requests & Code Reviews
- Every PR must have at least **one peer review** before merging.
- Ensure all merge conflicts are resolved locally before requesting review.
- Test your changes locally before submitting a PR.

---

## 4. Security & Secret Management (CRITICAL)
- **NEVER COMMIT API KEYS OR SECRETS.**
- Ensure `.env` is never staged (`git status` before committing).
- Always use `.env.example` as a template for new required environment variables.
- If a secret is accidentally committed, notify the team immediately to rotate the key and rewrite git history.
