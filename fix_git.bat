@echo off
echo grocery-489414-4c07bb70f399.json >> .gitignore
git rm --cached grocery-489414-4c07bb70f399.json
git add .gitignore
git commit --amend -m "Update: Operacion Unicornio Blanco y metricas (sin secret)"
git push origin master
