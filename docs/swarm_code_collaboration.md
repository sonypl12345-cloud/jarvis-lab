# Swarm Code Collaboration — LAB v0.1

This is a **proposed** coding-team workflow for Jarvis Lab, not a running
multi-agent coding service. It adds a deterministic, advisory change gate.
It does not start LLMs, execute agent-generated code, access Supabase, push
commits, deploy anything, or merge pull requests.

## One codebase, multiple isolated changes

1. **Planner** receives a user-approved goal, reads existing modules and
   outlines a narrow change and acceptance tests.
2. **Coder** works in a task branch or its own Git worktree, touching only
   assigned files.
3. **Tester** executes deterministic tests on the exact proposed commit.
4. **Reviewer** works in a fresh context, checks the diff, adverse cases,
   privacy and scope.
5. **Integrator** verifies GitHub's actual diff, CI status, review and the
   user's approval, and decides whether to merge. The integrator is NOT
   replaced by a self-reported manifest.

Every role may use the **same local model sequentially** to minimize RAM/VRAM
use. Different role sessions are not proof of truly independent judgment.
An external test runner and owner merge approval remain necessary.

## How to keep tasks coordinated

- Existing GENESIS shared memory/forum: reasoning notes and verified outcomes.
- Existing GENESIS resource leases: prevent overlapping ownership of a file
  or shared worker. Expire abandoned claims instead of forcing locks.
- Git task branches/worktrees: actual code and history; only Git is the source
  of truth for file content and the final diff.
- Draft pull requests: integration review, one at a time.
- Only verified test receipts and an explicit owner decision may promote a
  change. Never treat agent text as permission to merge/deploy.

**Do not put live credentials, host paths, device IDs, private chat content,
tokens, screenshots, or production bridge source in this public repository.**

## Change manifest screening

The stdlib-only scanner accepts a local JSON manifest:

- schema = JARVIS_SWARM_PR_LAB/0.1
- task_id, repository, base_sha, head_sha
- mode = LAB_ONLY, production_change = false, secret_data = false
- changed_paths: relative files in src/, tests/, docs/, examples/
- roles: planner, coder, tester, reviewer (distinct session IDs)
- tests: PASS receipts tied to head_sha and tester session
- review: APPROVE receipt tied to head_sha and reviewer session

Run:

```bash
python -m unittest discover -s tests -v
python src/swarm_review_gate_v01.py path/to/manifest.json
```

A successful scan returns **CANDIDATE_NEEDS_EXTERNAL_CHECKS** and
**merge_allowed = false**. This is *not* validation of the truth of the
claims in the manifest. GitHub CI must independently verify the real
commit, test status and reviewer, then the owner decides.

## Staged adoption

**Stage 1 (this draft):** manifest scanner, tests and collaboration protocol
with no model calls, no production writes and no merge authority.

**Stage 2:** use the already-installed local model through a narrow,
resource-limited adapter on the owner's laptop, one role at a time.
Verify the existing official GENESIS worker rather than creating a second
runtime or background daemon. Read code only from a trusted checkout.

**Stage 3:** connect read-only discovery and claim/release to the existing
GENESIS Supabase coordination, without new tables or blanket grants.
Create draft Git branches/PRs only on explicit task approval.

**Stage 4:** add measured quality gates and replayable regressions.
Never allow a model to approve its own patch or alter the merge policy.


## Reusing external agents (one repository, no second brain)

External agents are replaceable specialists behind the **existing** GENESIS
Free Agent Broker, not independent owners of the codebase. A ticket must
include a public repository, exact base commit SHA, task ID, assigned role,
limited paths and a response-size budget. The provider's answer is untrusted
text, not permission to execute code or merge a PR.

Example ticket (the host independently verifies the SHA and GitHub scope):

```json
{
  "schema": "JARVIS_SWARM_TICKET/0.1",
  "task_id": "lab-review-001",
  "repository": "example/jarvis-lab",
  "base_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "visibility": "PUBLIC",
  "role": "reviewer",
  "allowed_paths": ["src/swarm_review_gate_v01.py"],
  "max_response_chars": 1000
}
```

Example normalized external response:

```json
{
  "schema": "JARVIS_SWARM_EXTERNAL_ADVICE/0.1",
  "task_id": "lab-review-001",
  "repository": "example/jarvis-lab",
  "base_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "role": "reviewer",
  "provider": "external-reviewer-01",
  "paths": ["src/swarm_review_gate_v01.py"],
  "advice": "Consider additional test cases for nested sensitive filenames."
}
```

Call `assess_external_advice(ticket, report)` from the existing
`src/swarm_review_gate_v01.py`. Even with all fields validated, the
result is **QUARANTINED_ADVISORY_ONLY**, and code execution, commit,
and merge authority remain **false**. The provider label and advice
are unverified; check actual GitHub sources and independently test any
human/integrator-prepared patch.

A provider may be unavailable, unauthenticated, unable to inspect a
small repository, or may return misleading advice. The broker must
route such results to HOLD and use a different available specialist
only with a fresh scoped ticket. Never send private repositories,
tokens, device credentials, or personal project memory to free
third-party services.

For a single project, use one authoritative Git repository, per-task
branches, test-first CI and one integration decision. Do not allow
simultaneous direct writes by outside agents to the same branch.
