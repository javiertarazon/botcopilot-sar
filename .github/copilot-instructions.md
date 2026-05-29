# Copilot Coding Agent instructions

Este repositorio consume guías de trabajo (“superpowers”) sincronizadas desde `javiertarazon/superpowers`.

## Cómo usar las superpowers

- Antes de responder o ejecutar cambios, identifica si aplica alguna guía de `.github/superpowers/skills/*/SKILL.md` y síguela.
- Si la tarea implica planificar, usa primero la guía de planificación (p. ej. `writing-plans` o `executing-plans`).
- Si la tarea es un bug, usa `systematic-debugging`.
- Si la tarea es refactor/feature con riesgo, usa `test-driven-development` y verifica antes de finalizar (`verification-before-completion`).
- Si la tarea implica múltiples hilos independientes, usa `dispatching-parallel-agents`/`subagent-driven-development`.
- Si recibes o solicitas review, usa `receiving-code-review`/`requesting-code-review`.

## Fuente de verdad

- No edites a mano `.github/superpowers/**`; se actualiza por workflow.
