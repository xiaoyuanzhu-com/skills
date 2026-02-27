# Skills

Personal skills for [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

## Structure

```
skills/
├── skills/
│   ├── apple-health/     # Health & fitness data analysis
│   └── .../              # More skills to come
├── template/
│   └── SKILL.md          # Starter template for new skills
└── README.md
```

## Usage

Install a skill in Claude Code:

```
/skill install github:xiaoyuanzhu-com/skills/skills/<skill-name>
```

## Creating a New Skill

Copy `template/SKILL.md` into a new directory under `skills/` and fill in the frontmatter and instructions.

See the [Agent Skills spec](https://github.com/anthropics/skills/tree/main/spec) for details.
