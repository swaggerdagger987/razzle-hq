# Graveyard

Frozen snapshots of predecessor repos. **Read-only reference quarries** — do not import from these paths into active `apps/`, `packages/`, or `spec/` code.

| Directory | Source | Snapshot commit | Snapshot date |
|-----------|--------|-----------------|---------------|
| `razzle/` | [swaggerdagger987/razzle](https://github.com/swaggerdagger987/razzle) | `9b72877943e59b1fa0d92fa658bd78287bd83033` | 2026-06-09 |
| `FDL/` | [swaggerdagger987/FDL](https://github.com/swaggerdagger987/FDL) | `467ecc6095745365ea570273d5ee3439290129c2` | 2026-03-08 |
| `razzle-legacy/` | [swaggerdagger987/razzle-legacy](https://github.com/swaggerdagger987/razzle-legacy) | — | **unavailable** |

## razzle-legacy

`swaggerdagger987/razzle-legacy` no longer exists on GitHub (404 as of 2026-06-25). Its ADRs and domain spine were absorbed into `spec/STACK.md` when razzle-hq was seeded. If a local or archived copy surfaces, drop it in `graveyard/razzle-legacy/` and update this table.

## Rules

1. Agents may read `graveyard/` for proven patterns; never wire imports or bridges from it.
2. No active doc or code may depend on graveyard paths at runtime.
3. To refresh a snapshot: re-clone the upstream repo, copy the tree (excluding `.git`), update the commit SHA in this README, commit.
4. **Secrets redacted:** `razzle/legacy/.env` contained an API key in upstream; only `.env.example` is kept here.
