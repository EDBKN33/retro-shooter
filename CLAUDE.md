# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Git Workflow

After completing any meaningful unit of work, commit the changes and push to GitHub.

```bash
git add <specific-files>
git commit -m "Short, descriptive message explaining what and why"
git push origin master
```

Commit messages should be concise and describe the change (e.g. `add shield power-up to shooter`, `fix speeder zigzag going out of bounds`). Never bundle unrelated changes into one commit.

## Related Repositories

- **claude-code-workspace** — All Claude skills, subagents, and design reference: github.com/EDBKN33/claude-code-workspace
- **product-council** — ProductCouncil 4-AI deliberation system: github.com/EDBKN33/product-council

## Running the Games

These are standalone HTML files with no build step, dependencies, or server required. Open directly in a browser:

- `shooter.html` — Retro top-down arcade shooter
- `tictactoe.html` — Two-player Tic Tac Toe

## Architecture

Both games are self-contained single-file HTML documents with inline CSS and JavaScript. There is no module system, bundler, or external dependencies.

### shooter.html

A canvas-based game (800×600) using a fixed game loop driven by `requestAnimationFrame`.

**Core architecture:**
- **State machine** — `STATES` enum (`MENU`, `PLAYING`, `LEVEL_COMPLETE`, `GAME_OVER`, `PAUSED`, `HOW_TO_PLAY`) controls which screen is rendered each frame
- **Game loop** — `gameLoop(timestamp)` computes `dt` (delta time in seconds, capped at 0.05s) and dispatches update+draw per state
- **Entity classes** — `Player`, `Bullet`, `Enemy` (base), `CrawlerEnemy`, `TankEnemy`, `SpeederEnemy`, `ShooterEnemy` — all hold their own state and expose `update(dt)` / `draw()` methods
- **Wave/level manager** — `LEVEL_DATA` array defines 5 levels with wave compositions; `updateWaveManager(dt)` handles spawn queues, wave progression, and level completion transitions
- **Collision** — `checkCollisions()` runs circle-circle detection between bullets↔enemies and bullets/enemies↔player each frame
- **Obstacles** — Static rect definitions in `OBSTACLE_DEFS`; `resolveObstacleCollision()` pushes entities out using minimum overlap axis
- **Input** — Global `keys` object (keyboard) and `mouse` object updated via event listeners; `clickConsumed` flag prevents multi-button clicks in one frame

**Score values:** Crawler=10, Speeder=20, ShooterEnemy=25, Tank=30

### tictactoe.html

Simple DOM-based game. State is a 9-element array (`board`). Win detection checks all 8 combinations in `WINS`. Score persists across restarts within the same session.
