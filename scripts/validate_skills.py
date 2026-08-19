#!/usr/bin/env python3
"""Validate the reBot Arm skills repository structure.

Checks:
1. Every directory under skills/ contains a SKILL.md
2. SKILL.md frontmatter is valid YAML and contains name + description
3. frontmatter name matches the directory name
4. Every skill listed in README.md's index table has a real SKILL.md
5. Repo root files exist (README.md, AGENTS.md, docs/skill-authoring-guide.md)
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # repo root (scripts/ -> ..)
SKILLS = ROOT / "skills"

errors = []
warnings = []


def check_frontmatter(path: Path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        errors.append(f"{path}: missing YAML frontmatter")
        return None
    fm = m.group(1)
    name = re.search(r"^name:\s*(.+)$", fm, re.M)
    desc = re.search(r"^description:\s*(.+)$", fm, re.M)
    if not name:
        errors.append(f"{path}: frontmatter missing 'name'")
    if not desc:
        errors.append(f"{path}: frontmatter missing 'description'")
    if not name:
        return None
    return name.group(1).strip().strip('"').strip("'")


def main():
    if not SKILLS.is_dir():
        errors.append(f"{SKILLS}: skills directory not found")
        sys.exit(1)

    skill_dirs = sorted(
        p for p in SKILLS.iterdir() if p.is_dir() and not p.name.startswith(".")
    )
    if not skill_dirs:
        errors.append("skills/: no skill directories found")
        sys.exit(1)

    for d in skill_dirs:
        sk = d / "SKILL.md"
        if not sk.exists():
            errors.append(f"{sk}: missing SKILL.md")
            continue
        fm_name = check_frontmatter(sk)
        if fm_name and fm_name != d.name:
            errors.append(
                f"{sk}: frontmatter name '{fm_name}' != directory name '{d.name}'"
            )
        # Soft checks: AI-usage quality (warnings, not errors)
        text = sk.read_text(encoding="utf-8")
        if not re.search(r"🤖|👤|🔀", text):
            warnings.append(f"{d.name}: no AI/user division markers (🤖/👤/🔀)")
        if not re.search(r"验证|预期结果", text):
            warnings.append(f"{d.name}: no '验证/预期结果' content")

    # README index table cross-check
    readme = ROOT / "README.md"
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        listed = re.findall(r"skills/([a-z0-9-]+)/SKILL\.md", text)
        for s in listed:
            if not (SKILLS / s / "SKILL.md").exists():
                errors.append(f"README lists skills/{s}/SKILL.md but it does not exist")
        for d in skill_dirs:
            if d.name not in listed:
                warnings.append(f"skill '{d.name}' not listed in README index table")

    for f in ["README.md", "AGENTS.md", "docs/skill-authoring-guide.md",
              "memory/local-machine-env.md"]:
        if not (ROOT / f).exists():
            errors.append(f"{f}: missing")

    # Workflows and references (soft)
    for f in ["workflows/first-run.md", "workflows/first-imitation-task.md",
              "workflows/vision-grasping-project.md",
              "references/fault-codes.md", "references/os-matrix.md"]:
        if not (ROOT / f).exists():
            warnings.append(f"{f}: missing (recommended)")

    print(f"skills checked: {len(skill_dirs)}")
    for w in warnings:
        print(f"WARN: {w}")
    if errors:
        print("ERRORS:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print("OK: repository structure valid")


if __name__ == "__main__":
    main()
