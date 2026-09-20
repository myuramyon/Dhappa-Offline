# DHAPPA Design System

## Product direction
Research-grade analytics with an operational cockpit. Important context appears first; technical depth stays available on demand.

## Tokens
- Spacing: 4, 8, 16, 24, 32, 48px
- Surfaces: `--bg`, `--panel`, `--panel-alt`, `--panel-soft`
- Text: primary `--text`, secondary `--muted`
- Semantic: green for ready/pass, amber for moderate/change, red for errors, blue/green-neutral for selected and informational states
- Radius: 7px controls, 9-12px cards, 14px hero surfaces
- Control height: 38-42px
- Card padding: 16-20px
- Table row padding: 10-12px
- Focus: 2px accent outline with 2px offset

## Components
Shared shell, sidebar navigation, compact target header, page hero, status badge, summary metric strip, house card, engine registry, daily table, pagination, import preview, loading state, error state, modal dialog, advanced disclosure.

## Hierarchy
Page context -> target/data status -> primary result -> supporting metrics -> advanced technical detail.

## Responsive rules
Desktop uses a 238px sidebar and four equal house cards. Tablet uses a compact 76px sidebar and two-column house cards. Mobile uses a 58px sidebar and single-column content with horizontally scrollable tables.
