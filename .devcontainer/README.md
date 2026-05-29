# Codespaces

Al abrir este repo en GitHub Codespaces, se ejecuta `.devcontainer/postCreate.sh` para:

- Crear/usar la venv local `.venv/` (persistente en el workspace)
- Instalar dependencias desde `requirements-codespace.txt`

Notas:
- `.venv/` está en `.gitignore` y **no** debe commitearse.
- Si cambias dependencias, actualiza `requirements-codespace.txt`.

